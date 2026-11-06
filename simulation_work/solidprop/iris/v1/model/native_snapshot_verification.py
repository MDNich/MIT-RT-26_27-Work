"""Correct the capacity setting, independently assemble the printed sector, and audit real exports."""
import argparse
import itertools
import json
from pathlib import Path
import re
import tempfile

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu

from continuous_heating_campaign import digest
from ops import ROOT, TMP, atomic, disks, utc
from prepare_native_wall_snapshots import PACKAGE as ORIGINAL

PACKAGE = ORIGINAL.with_name(ORIGINAL.name + '_r2')
CASES = ('sustainer_al', 'sustainer_cf', 'booster_al', 'booster_cf')
MANUAL = 'https://ansyshelp.ansys.com/public/views/secured/corp/v261/en/ans_elem/Hlp_E_SOLID278.html'
CORNERS = np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
                    [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])


def sector_reference(deck, expected):
    """Read numbers from the actual APDL text. Use full brick quadrature and no radial reduction."""
    nodes, elements, initial, loads, sources, props = {}, {}, {}, {}, {}, {}
    if deck.count('KEYOPT,1,15,2\n') != 1 or deck.count('TINTP,,,,1\n') != 1:
        raise ValueError('The heat-capacity and backward-Euler settings must be explicit')
    for line in deck.splitlines():
        cmd, *fields = line.split(',')
        if cmd == 'MP':
            prop, material, value = fields
            props.setdefault(int(material), {})[prop] = float(value)
        elif cmd == 'MAT':
            mat = int(fields[0])
        elif cmd == 'N':
            idx = int(fields[0])
            if idx in nodes: raise ValueError('Repeated node')
            nodes[idx] = list(map(float,fields[1:]))
        elif cmd == 'EN':
            idx = int(fields[0])
            if idx in elements: raise ValueError('Repeated brick')
            elements[idx] = (mat, np.array(fields[1:],dtype=int)-1)
        elif cmd == 'IC':
            idx, label, val = fields
            if label != 'TEMP' or int(idx) in initial: raise ValueError('Unexpected initial condition')
            initial[int(idx)] = float(val)
        elif cmd == 'F':
            idx, label, val = fields
            if label != 'HEAT' or int(idx) in loads: raise ValueError('Unexpected thermal force')
            loads[int(idx)] = float(val)
        elif cmd == 'BFE':
            idx, label, start, *vals = fields
            key = (int(idx),int(start))
            if label != 'HGEN' or key in sources or len(vals)!=4: raise ValueError('Unexpected body source')
            sources[key] = list(map(float,vals))
    n = expected['nodes']
    if nodes.keys() != set(range(1,n+1)) or initial.keys()!=nodes.keys() or len(elements)!=expected['elements']:
        raise ValueError('The printed topology or initial field is incomplete')
    xyz = np.array([nodes[i] for i in range(1,n+1)])
    t0 = np.array([initial[i] for i in range(1,n+1)])
    rhs = np.array([loads.get(i,0.) for i in range(1,n+1)])
    conn = np.array([v[1] for v in elements.values()])
    mats = [props[m] for m,_ in elements.values()]
    k = np.array([p['KXX'] for p in mats])
    cap = np.array([p['DENS']*p['C'] for p in mats])
    if min(cap)<=0 or min(k)<=0: raise ValueError('Invalid material')
    source = np.array([sources.get((i,1),[0.]*4)+sources.get((i,5),[0.]*4) for i in elements])
    ke = np.zeros((len(conn),8,8))
    ce = np.zeros_like(ke)
    for local in itertools.product([-1/np.sqrt(3.),1/np.sqrt(3.)],repeat=3):
        factors = 1.+CORNERS*np.array(local)
        shape = np.prod(factors,axis=1)/8.
        deriv = np.stack([CORNERS[:,j]*np.prod(np.delete(factors,j,axis=1),axis=1)/8. for j in range(3)],axis=1)
        jacobian = xyz[conn].transpose(0,2,1) @ deriv
        volume = np.linalg.det(jacobian)
        if min(volume)<=0: raise ValueError('Inverted or singular brick')
        grad = deriv @ np.linalg.inv(jacobian)
        ke += (k*volume)[:,None,None]*(grad @ grad.transpose(0,2,1))
        ce += (cap*volume)[:,None,None]*np.outer(shape,shape)
        np.add.at(rhs,conn,((source @ shape)*volume)[:,None]*shape)
    rows = np.repeat(conn,8,axis=1).ravel()
    cols = np.tile(conn,(1,8)).ravel()
    def assemble(values):
        return coo_matrix((values.ravel(),(rows,cols)),shape=(n,n)).tocsc()
    mass = assemble(ce)
    dt = .005
    lu = splu(mass/dt+assemble(ke))
    t = t0.copy()
    weights = mass.sum(axis=0).A.ravel()
    history = []
    for _ in range(10):
        t = lu.solve(mass@t/dt+rhs)
        history.append(t)
    ref = np.repeat(expected['consistent_expected_C'],expected['ring_nodes'],axis=1)
    series = np.array(history)
    mismatch = abs(series-ref).max()
    power = rhs.sum()
    if mismatch>1e-6 or abs(.05*power-expected['input_energy_J_per_sector'])>1e-10:
        raise ValueError(f'Deck/reference discrepancy: {mismatch:g} K, {power:g} W')
    return dict(capacity_weight_J_K=weights.tolist(),initial_C=t0.tolist(),sector_power_W=float(power),
                independent_3d_error_K=float(mismatch),
                max_3d_energy_error_J=float(abs((series-t0)@weights-np.arange(1,11)*dt*power).max()))


def prepare(verify):
    original = json.loads((ORIGINAL/'manifest.json').read_text())
    if not verify and PACKAGE.exists(): raise FileExistsError('Revision 2 already sealed')
    with tempfile.TemporaryDirectory(dir=ORIGINAL.parent) as temp:
        stage = Path(temp)/'package'
        stage.mkdir()
        jobs = {}
        for name in CASES:
            parent = ORIGINAL/(name+'.json')
            e = json.loads(parent.read_text())
            source = ORIGINAL/(name+'.inp')
            if digest(parent)!=original['jobs'][name] or digest(source)!=e['deck_sha256']:
                raise ValueError('Unexpected snapshot predecessor')
            deck = source.read_text().replace('ET,1,SOLID278\n','ET,1,SOLID278\nKEYOPT,1,15,2\n')
            deck = deck.replace('TRNOPT,FULL\n','TRNOPT,FULL\nTINTP,,,,1\n')
            path = stage/source.name
            path.write_text(deck,encoding='ascii')
            info = sector_reference(deck,e)
            atomic(stage/parent.name,dict(case=name,deck_sha256=digest(path),parent_sha256=digest(parent),
                    max_energy_error_J=2e-7,max_transverse_spread_K=.002,**info))
            jobs[name] = digest(stage/parent.name)
        atomic(stage/'manifest.json',dict(parent_manifest_sha256=digest(ORIGINAL/'manifest.json'),jobs=jobs,
              capacity='Explicit SOLID278 KEYOPT(15)=2',integration='Backward Euler',manual=MANUAL,
              scope='Frozen 30 s material and loads. No native execution in this receipt.'))
        if verify:
            if {p.name for p in stage.iterdir()}!={p.name for p in PACKAGE.iterdir()}:
                raise ValueError('Package file set mismatch')
            for p in stage.iterdir():
                if p.read_bytes()!=(PACKAGE/p.name).read_bytes(): raise ValueError('Package differs: '+p.name)
        else: stage.rename(PACKAGE)


def evaluate(field, e, check):
    n, ring = e['nodes'],e['ring_nodes']
    if field.shape!=(10*n,4) or not np.isfinite(field).all(): raise ValueError('Invalid export shape or values')
    blocks = field.reshape(10,n,4)
    steps = np.arange(1,11)[:,None]
    if not np.all(blocks[:,:,0]==steps) or not np.all(blocks[:,:,1]==np.arange(1,n+1)):
        raise ValueError('Missing, duplicate or reordered identifiers')
    if np.max(abs(blocks[:,:,2]-.005*steps))>1e-10: raise ValueError('Wrong native time')
    t = blocks[:,:,3]
    primary = np.repeat(e['consistent_expected_C'],ring,axis=1)
    error = np.max(abs(t-primary))
    spread = np.ptp(t.reshape(10,-1,ring),axis=2).max()
    residual = (t-check['initial_C'])@check['capacity_weight_J_K']-steps.ravel()*.005*check['sector_power_W']
    if error>e['criterion_max_nodal_error_K'] or spread>check['max_transverse_spread_K'] or max(abs(residual))>check['max_energy_error_J']:
        raise ValueError(f'Temperature, symmetry or energy failed: {error:g} K, {spread:g} K, {max(abs(residual)):g} J')
    return dict(max_nodal_error_K=float(error),max_ring_spread_K=float(spread),
                max_energy_residual_J=float(max(abs(residual))),fields=10,nodes_per_field=n,passed=True)


def records(name):
    parent = ORIGINAL/(name+'.json')
    corrected = PACKAGE/parent.name
    check = json.loads(corrected.read_text())
    if digest(corrected)!=json.loads((PACKAGE/'manifest.json').read_text())['jobs'][name] or digest(parent)!=check['parent_sha256']:
        raise ValueError('Sealed comparison changed')
    return json.loads(parent.read_text()),check


def fixture():
    evidence = {}
    for name in CASES:
        e,check = records(name)
        n = e['nodes']
        times = np.arange(1,11)
        t = np.repeat(e['consistent_expected_C'],e['ring_nodes'],axis=1)
        data = np.column_stack([np.repeat(times,n),np.tile(np.arange(1,n+1),10),np.repeat(.005*times,n),t.ravel()])
        evidence[name] = evaluate(data,e,check)
        faults = {'missing_step':data[:-n],'duplicate_id':data.copy(),'wrong_time':data.copy(),
                  'corrupt_node':data.copy(),'energy_drift':data.copy()}
        faults['duplicate_id'][1,1] = 1.
        faults['wrong_time'][-1,2] += .001
        faults['corrupt_node'][n,3] += .5
        faults['energy_drift'][:,3] += .1
        for fault,bad in faults.items():
            try: evaluate(bad,e,check)
            except ValueError: continue
            raise RuntimeError('Fault passed: '+fault)
        evidence[name]['rejected'] = list(faults)
        evidence[name]['independent_3d_error_K'] = check['independent_3d_error_K']
    atomic(ROOT/'validation/native_snapshot_preflight.json',dict(cases=evidence,reader_sha256=digest(Path(__file__)),
        manifest_sha256=digest(PACKAGE/'manifest.json'),scope='Independent 3D assembly and synthetic reader checks only.'))


def audit(name,run):
    e,check = records(name)
    receipt = json.loads((run/'guest_terminal.json').read_text(encoding='utf-8-sig'))
    files = [name+'.out','snap_field.txt']
    if (receipt['job']!=name or receipt['exit_code']!=0 or receipt['guest_input_sha256'].lower()!=check['deck_sha256']
            or digest(run/(name+'.inp'))!=check['deck_sha256']):
        raise ValueError('Guest job or input differs')
    for f in files:
        if digest(run/f)!=receipt['guest_sha256'][f].lower(): raise ValueError('Guest export differs: '+f)
    log = (run/files[0]).read_text(errors='replace')
    if 'IRIS_FROZEN_SNAPSHOT_COMPLETE' not in log or 'RUN COMPLETED' not in log: raise ValueError('Incomplete native job')
    for kind in ('WARNING','ERROR'):
        if re.findall(rf'NUMBER OF {kind}\s+MESSAGES ENCOUNTERED=\s*(\d+)',log)!=['0'] or f'*** {kind} ***' in log:
            raise ValueError(f'Native {kind} requires review')
    for key,pattern in [('Number of processes requested',r'1\b'),('Number of threads per process requested',r'10\b'),
                        ('Total number of cores requested',r'10\s*\(Shared Memory Parallel\)')]:
        if not re.search(key+r'\s*:\s*'+pattern,log): raise ValueError('Incorrect parallel configuration')
    result = evaluate(np.loadtxt(run/files[1]),e,check)
    result.update(case=name,utc=utc(),files={f:digest(run/f) for f in files},source_sha256=e['source_sha256'],
                  terminal_sha256=digest(run/'guest_terminal.json'),manifest_sha256=digest(PACKAGE/'manifest.json'),
                  scope='Frozen 30 s motor state over 0.05 s. Native conduction and storage verification only.')
    atomic(ROOT/'validation'/('native_snapshot_r2_'+name+'.json'),result)


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','verify-input','fixture'])
    a = p.parse_args().action
    disks()
    if a=='fixture': fixture()
    else: prepare(a=='verify-input')

"""Check every exported moving-char FE step against the manufactured wall law."""
import argparse
import json
import math
import re
from pathlib import Path

import numpy as np

from continuous_heating_campaign import digest
from coupler import char_rate
from ops import ROOT, TMP, atomic, disks, utc
from prepare_native_moving_char import PACKAGE, PARENT


def evaluate(expected, law, steps, field):
    # Arrays are checked before index conversion to prevent rounding malformed
    # records to valid node or step IDs.
    if steps.ndim!=2 or steps.shape[1]!=8 or field.ndim!=2 or field.shape[1]!=5:
        raise ValueError('Unexpected native export dimensions')
    if not np.isfinite(steps).all() or not np.isfinite(field).all():
        raise ValueError('Nonfinite MAPDL data')
    n=expected['radial_cells']
    nodes=expected['nodes']
    ring=expected['ringsize']
    if len(field)!=len(steps)*nodes or not np.array_equal(steps[:,0],np.arange(1,len(steps)+1)):
        raise ValueError('Incomplete step or field history')
    ri,ro=expected['inner_m'],expected['outer_m']
    geom=expected['radial_correction']
    phi=math.radians(expected['angle_deg'])/expected['angular_divisions']
    chord=2*math.sin(phi/2)*expected['angular_divisions']*expected['length_m']
    rho=expected['rho_kg_m3']
    initial_mass=rho*chord*geom*(ro-ri)*(ro+ri)/2
    spent=0.
    elapsed=0.
    previous_r=ri
    worst_temp=worst_spread=mass_error=map_error=0.
    previous_rings=previous_temp=None
    limit=expected['preregistered']
    for i,line in enumerate(steps):
        step,t,dt,solver_t,r,new_r,j,ts=line
        if not (0.<dt<=expected['dt_ceiling_s']+1e-9 and r<new_r<=ro+1e-10):
            raise ValueError('Invalid duration or front travel')
        if abs(t-elapsed-dt)>2e-8 or abs(dt-solver_t)>2e-9 or abs(previous_r-r)>2e-10:
            raise ValueError('Noncontiguous native time, solve time or position')
        block=field[i*nodes:(i+1)*nodes]
        if not np.all(block[:,0]==step) or not np.array_equal(block[:,1],np.arange(1,nodes+1)):
            raise ValueError('Missing, duplicate or reordered node/step rows')
        radius=np.linspace(r,ro,n+1)
        if np.max(abs(block[:,2]-np.repeat(radius,ring)))>8e-11:
            raise ValueError('Field exported on an unexpected geometry')
        start=block[:,3].reshape(n+1,ring)
        end=block[:,4].reshape(n+1,ring)
        exact=expected['initial_face_C']+expected['slope_K']*np.log(radius/ri)
        worst_temp=max(worst_temp,np.max(abs(end-exact[:,None])),np.max(abs(start-exact[:,None])))
        worst_spread=max(worst_spread,np.max(np.ptp(end,axis=1)))
        if previous_rings is not None:
            # Compare all remapped nodal starting values to the preceding FE field.
            mapped=np.column_stack([np.interp(np.log(radius),np.log(previous_rings),previous_temp[:,k])
                                    for k in range(ring)])
            map_error=max(map_error,np.max(abs(mapped-start)))
        if abs(ts-np.mean(start[0]))>1e-5 or abs(j-char_rate(ts,law))>2e-8*max(j,1e-12):
            raise ValueError('Surface law differs from the exported start field')
        if abs(new_r-r-dt*j/(rho*geom))>1.5e-10:
            raise ValueError('Native front displacement differs from consumed char')
        spent+=.5*(r+new_r)*chord*dt*j
        retained=rho*geom*chord*(ro-new_r)*(ro+new_r)/2
        mass_error=max(mass_error,abs(spent+retained-initial_mass)/initial_mass)
        previous_r,elapsed=new_r,t
        previous_rings,previous_temp=radius,end
    difference=abs(elapsed-expected['exact_event_s'])/expected['exact_event_s']
    if abs(previous_r-ro)>1e-11 or difference>limit['max_relative_event_time']:
        raise ValueError('End radius or event time fails the predeclared target')
    if worst_temp>limit['max_field_error_K'] or worst_spread>limit['max_transverse_spread_K'] or map_error>.001:
        raise ValueError('Field error, transverse variation or remap error exceeds its target')
    if mass_error>limit['max_relative_mass_imbalance']:
        raise ValueError('Transient retained-plus-expelled char exceeds mass tolerance')
    return dict(passed=True,steps=len(steps),event_s=elapsed,analytic_s=expected['exact_event_s'],
                event_relative_error=difference,max_nodal_error_K=worst_temp,peak_transverse_spread_K=worst_spread,
                max_remap_readback_error_K=map_error,max_mass_relative_error=mass_error)


def fixture(e,law):
    r=e['inner_m']
    ro=e['outer_m']
    rows,fields=[],[]
    t=0.
    while r<ro:
        temps=e['initial_face_C']+e['slope_K']*np.log(np.linspace(r,ro,e['radial_cells']+1)/e['inner_m'])
        j=char_rate(temps[0],law)
        speed=j/(e['rho_kg_m3']*e['radial_correction'])
        dt=min(e['dt_ceiling_s'],(ro-r)/speed)
        new=min(ro,r+dt*speed)
        t+=dt
        idx=len(rows)+1
        rows.append([idx,t,dt,dt,r,new,j,temps[0]])
        for node in range(e['nodes']):
            ir=node//e['ringsize']
            fields.append([idx,node+1,r+(ro-r)*ir/e['radial_cells'],temps[ir],temps[ir]])
        r=new
    rows,fields=np.array(rows),np.array(fields)
    base=evaluate(e,law,rows,fields)
    for col in [0,1,2,3,4]:
        bad=fields.copy()
        bad[len(bad)//2,col]+=1.
        try: evaluate(e,law,rows,bad)
        except ValueError: continue
        raise RuntimeError(f'Corrupted field column {col} passed')
    return base


def audit(n):
    job=f'mvchar{n}'
    e=json.loads((PACKAGE/f'{job}.json').read_text())
    run=TMP/'runs'/('moving_char_log_r4_'+job)
    files=[job+'.out','moving_steps.txt','moving_field.txt']
    receipt=json.loads((run/'guest_terminal.json').read_text(encoding='utf-8-sig'))
    assert receipt['job']==job and receipt['exit_code']==0 and receipt['guest_input_sha256'].lower()==e['deck_sha256']
    assert digest(run/(job+'.inp'))==e['deck_sha256']
    for f in files: assert digest(run/f)==receipt['guest_sha256'][f].lower()
    log=(run/files[0]).read_text(errors='replace')
    assert e['terminal_marker'] in log and 'RUN COMPLETED' in log
    for kind in ('WARNING','ERROR'):
        assert re.findall(rf'NUMBER OF {kind}\s+MESSAGES ENCOUNTERED=\s*(\d+)',log)==['0'] and f'*** {kind} ***' not in log
    for key,count in [('Number of processes requested',1),('Number of threads per process requested',10)]:
        assert re.search(key+rf'\s*:\s*{count}\b',log)
    assert re.search(r'Total number of cores requested\s*:\s*10\s*\(Shared Memory Parallel\)',log)
    law=json.loads(PARENT.read_text())['cases'][0]['configuration']['char_law']
    result=evaluate(e,law,np.loadtxt(run/files[1]),np.loadtxt(run/files[2]))
    result.update(checked_utc=utc(),expected_sha256=digest(PACKAGE/f'{job}.json'),
                  reader_sha256=digest(__file__),receipt_sha256=digest(run/'guest_terminal.json'),
                  exports={f:digest(run/f) for f in files},
                  scope='Native manufactured continuously receding pure char. Full reacting-liner and energy comparison pending.')
    atomic(ROOT/'validation'/f'native_moving_char_r4_{job}.json',result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('fixture','audit'))
    parser.add_argument('--cells',type=int,choices=(8,16))
    a=parser.parse_args()
    disks()
    if a.action=='audit':
        if a.cells is None: parser.error('Specify the archived resolution')
        print(audit(a.cells))
        return
    law=json.loads(PARENT.read_text())['cases'][0]['configuration']['char_law']
    results={n:fixture(json.loads((PACKAGE/f'mvchar{n}.json').read_text()),law) for n in (8,16)}
    atomic(ROOT/'validation/moving_char_r4_reader_fixtures.json',dict(checked_utc=utc(),reader_sha256=digest(__file__),
        package_manifest_sha256=digest(PACKAGE/'manifest.json'),manufactured=results,
        scope='Synthetic arrays only, complete history and five rejected corruption types per resolution. No native execution.'))
    print('Two synthetic native-history fixtures and ten corrupted-field rejection checks passed.')


if __name__=='__main__': main()

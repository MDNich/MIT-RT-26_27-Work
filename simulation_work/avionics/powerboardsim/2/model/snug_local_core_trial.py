"""Benchmark the local fixture's initial clamp ramp at twelve SMP cores against its archived four-core solve."""
import argparse
import hashlib
import re

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from stage_local_jobs import seal
from stage_snug_fit import AUDIT, INPUTS

PARENT='snug125_nylon_lateral_friction_locked_pin1_m15'
CASE='snug125_nylon_clamp_smp12'


def stage():
    spec=read(AUDIT/'local_inputs_m15.json')[PARENT]
    cfg=INPUTS/PARENT/'local_job.json';verified(cfg,spec['spec_sha256'])
    assert read(cfg)['cores']==4
    original=INPUTS/PARENT/'model.inp';verified(original,spec['input_sha256'])
    first=original.read_bytes().split(b'SOLVE\n*CFOPEN,preload_lock,csv')
    assert len(first)==2
    old=b'TIME,1\nNSUBST,20,1000,5\nF,2930,FZ,750\nF,3828,FZ,750\n'
    new=b'TIME,0.4\nNSUBST,8,400,2\nF,2930,FZ,300\nF,3828,FZ,300\n'
    assert first[0].endswith(old) and not re.search(rb'(?im)^solve\s*$',first[0])
    deck=first[0][:-len(old)]+new+b'SOLVE\nFINISH\n/POST1\nSET,LAST\n/COM,PB_CLAMP_SMP_TRIAL_COMPLETE\nFINISH\n/EXIT,NOSAVE\n'
    dest=INPUTS/CASE;dest.mkdir(exist_ok=True)
    checksum=seal(dest/'model.inp',deck)
    write_json(AUDIT/'local_core_trial_input.json',dict(case=CASE,parent=PARENT,parent_input_sha256=spec['input_sha256'],
               input_sha256=checksum,parent_spec_sha256=spec['spec_sha256'],mesh_sha256=spec['mesh_sha256'],
               parent_cores=4,trial_cores=12,parallel_mode='SMP',ramp_per_bolt_N_per_unit_load_time=750,
               first_dt=.05,min_dt=.001,max_dt=.2,final_load_time=.4,final_bolt_load_N=300,geometry_prefix_sha256=
               hashlib.sha256(first[0][:-len(old)]).hexdigest(),
               scope='Matched clamp increments only. This timing trial runs once in the serial queue.'))


def monitor(path):
    rows=[]
    for line in path.read_text(errors='replace').splitlines():
        col=line.split()
        if len(col)>=9 and all(x.isdigit() for x in col[:5]):
            if int(col[0])!=1:
                break
            rows.append([int(col[1]),int(col[2]),int(col[3]),int(col[4]),float(col[6]),float(col[7]),float(col[8])])
    result=np.array(rows)
    assert len(result)>=3 and np.all(np.diff(result[:,4])>0) and np.all(np.diff(result[:,5])>0)
    return result


def reaction(raw,k):
    force,node,dof=raw.nodal_reaction_forces(k)
    order=np.lexsort((dof,node))
    return np.stack([node[order],dof[order]],axis=1),force[order]


def audit(case,campaign):
    spec=read(AUDIT/'local_core_trial_input.json')
    assert case==spec['case']==CASE
    runs=[]
    for name,job,cores,expected in ((PARENT,'pull',4,spec['parent_input_sha256']),
                                   (CASE,'file',12,spec['input_sha256'])):
        folder=ROOT/'.runtime/archive'/campaign/name
        receipt=ROOT/'.runtime/receipts'/campaign/name
        ledger=read(receipt/'archived.json');status=read(receipt/'status.json')
        sha={r['name']:r['sha256'] for r in ledger['files']}
        assert ledger['case']==name and (receipt/'released.txt').is_file() and status['cores']==cores
        assert status['phase']=='solver_complete' and sha['model.inp']==expected
        for f in ['model.inp',job+'.rst',job+'.mntr','solve.out']:verified(folder/f,sha[f])
        listing=(folder/'solve.out').read_text(errors='replace')
        assert re.search(r'TOTAL OF\s+'+str(cores)+r' CORES REQUESTED',listing)
        if name==CASE:
            assert status['exit']==0 and 'PB_CLAMP_SMP_TRIAL_COMPLETE' in listing
            assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',listing)
        raw=reader.read_binary(str(folder/(job+'.rst')))
        runs.append((raw,monitor(folder/(job+'.mntr')),sha[job+'.rst'],sha[job+'.mntr']))
    (parent,p,psha,pm),(trial,t,tsha,tm)=runs
    assert np.array_equal(trial.mesh.nnum,parent.mesh.nnum) and np.array_equal(trial.mesh.nodes,parent.mesh.nodes)
    assert np.array_equal(trial.mesh.enum,parent.mesh.enum)
    assert abs(trial.time_values[-1]-.4)<1e-8
    compare=[]
    for i,row in enumerate(t):
        hits=np.flatnonzero(np.isclose(p[:,4],row[4],rtol=0,atol=1e-7))
        if not len(hits):continue
        j,=hits
        assert i==j and np.array_equal(row[:4],p[j,:4])
        ids,u=trial.nodal_displacement(i);other,v=parent.nodal_displacement(j)
        assert np.array_equal(ids,other) and np.array_equal(np.isfinite(u),np.isfinite(v))
        mask=np.isfinite(u);error=float(abs(u[mask]-v[mask]).max())
        rt,f=reaction(trial,i);rp,g=reaction(parent,j)
        assert np.array_equal(rt,rp)
        relative=np.linalg.norm(f-g)/max(1.,np.linalg.norm(g))
        assert error<1e-6 and relative<1.e-4
        compare.append(dict(substep=i+1,load_time=row[4],cumulative_iterations=int(row[3]),
                            displacement_max_error_mm=error,reaction_relative_l2=float(relative),
                            four_core_elapsed_s=p[j,5],twelve_core_elapsed_s=row[5]))
    assert len(compare)>=3 and compare[0]['substep']==1
    assert [r['substep'] for r in compare]==list(range(1,len(compare)+1))
    first,last=compare[0],compare[-1]
    d4=last['four_core_elapsed_s']-first['four_core_elapsed_s']
    d12=last['twelve_core_elapsed_s']-first['twelve_core_elapsed_s']
    assert min(d4,d12)>0
    write_json(AUDIT/'local_core_trial.json',dict(case=CASE,campaign=campaign,parent=PARENT,parent_rst_sha256=psha,
               trial_rst_sha256=tsha,parent_monitor_sha256=pm,trial_monitor_sha256=tm,matched_ramp_states=compare,
               warm_four_core_seconds=d4,warm_twelve_core_seconds=d12,warm_factor=d4/d12,
               scope='Wall time over identical accepted warm increments on the same physical host. The matrix includes '
                     'the full case and fixtures. The moving cell has not begun lateral contact in this control.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('stage','audit'));p.add_argument('--campaign',default='nov08_01')
    args=p.parse_args()
    if args.action=='stage':stage()
    else:audit(CASE,args.campaign)

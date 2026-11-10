"""Benchmark the local fixture's initial clamp ramp at twelve SMP cores against its archived four-core solve."""
import argparse
import hashlib
import re

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from dpf_readback import export_file
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


def matched_stations(parent, trial):
    """Match the common clamp ramp before the shorter trial clips its final increment."""
    matches=[]
    for i,row in enumerate(trial):
        hits=np.flatnonzero(np.isclose(parent[:,4],row[4],rtol=0,atol=1e-7))
        if len(hits):
            j,=hits
            assert i==j and np.array_equal(row[:4],parent[j,:4])
            matches.append(i+1)
    assert len(matches)>=3 and matches==list(range(1,len(matches)+1))
    return matches


def clamp_fields(raw,path,out,sha,sets):
    """Read all available translations and rotations with the ANSYS result reader."""
    result={}
    rr=raw._resultheader['ls_table']
    for number in sets:
        assert list(rr[number-1,:2])==[1,number]
    for field,unit,suffix in [('U','mm','.u'),('ROT','rad','.rot')]:
        spec=dict(source_sha256=sha,sets=sets,field=field,unit=unit)
        folder=export_file(path,out/field,spec)
        fields=[];files={}
        for number in sets:
            stem=folder/f'set_{number:04d}'
            nodes=np.fromfile(stem.with_suffix('.ids'),'<i4')
            values=np.fromfile(stem.with_suffix(suffix),'<f8').reshape(-1,3)
            order=np.argsort(nodes)
            if fields:
                assert np.array_equal(nodes[order],ids)
            ids=nodes[order]
            fields.append(values[order])
            for ext in ('.ids',suffix,'.json'):
                f=stem.with_suffix(ext)
                files[f.name]=digest(f)
        assert np.isin(ids,raw.mesh.nnum).all()
        result[field]=dict(ids=ids,data=np.stack(fields),files=files)
    assert np.array_equal(result['U']['ids'],np.sort(raw._resultheader['neqv']))
    assert len(result['ROT']['ids'])>0 and np.isin(result['ROT']['ids'],result['U']['ids']).all()
    assert np.max(abs(result['U']['data']))>0 and np.max(abs(result['ROT']['data']))>0
    return result


def compare_states(first,second,sets):
    parent,fields,p=first
    trial,other,t=second
    assert np.array_equal(trial.mesh.nnum,parent.mesh.nnum) and np.array_equal(trial.mesh.nodes,parent.mesh.nodes)
    assert np.array_equal(trial.mesh.enum,parent.mesh.enum) and np.array_equal(trial.mesh._elem,parent.mesh._elem)
    for kind in ('U','ROT'):
        assert np.array_equal(fields[kind]['ids'],other[kind]['ids'])
    rows=[]
    for j,number in enumerate(sets):
        i=number-1
        assert np.isclose(parent.time_values[i],p[i,4],rtol=0,atol=5e-5)
        assert abs(parent.time_values[i]-trial.time_values[i])<1e-10
        error=float(abs(fields['U']['data'][j]-other['U']['data'][j]).max())
        rotation_error=float(abs(fields['ROT']['data'][j]-other['ROT']['data'][j]).max())
        rt,f=reaction(trial,i);rp,g=reaction(parent,i)
        assert np.array_equal(rt,rp)
        relative=float(np.linalg.norm(f-g)/max(1.,np.linalg.norm(g)))
        assert error<1e-6 and rotation_error<1e-6 and relative<1.e-4
        rows.append(dict(substep=number,load_time=t[i,4],cumulative_iterations=int(t[i,3]),
                         displacement_max_error_mm=error,rotation_max_error_rad=rotation_error,
                         reaction_relative_l2=relative,four_core_elapsed_s=p[i,5],twelve_core_elapsed_s=t[i,5]))
    return rows


def smp_threads(listing):
    workers,=set(map(int,re.findall(r'SINGLE PROCESS WITH\s+(\d+) THREADS? REQUESTED',listing)))
    requested,=set(map(int,re.findall(r'TOTAL OF\s+(\d+) CORES? REQUESTED',listing)))
    assert workers==requested
    return workers


def choose_cores(rows):
    """Prefer twelve only if both total warm time and the typical matched increment improve."""
    warm4=np.diff([r['four_core_elapsed_s'] for r in rows])
    warm12=np.diff([r['twelve_core_elapsed_s'] for r in rows])
    assert len(warm4)>=2 and np.all(warm4>0) and np.all(warm12>0)
    return 12 if warm12.sum()<warm4.sum() and np.median(warm12/warm4)<1 else 4


def verify_production_runtime(case,campaign,spec,status,listing):
    """Check the actual solver banner against the case receipt, including older four-core runs."""
    cores=smp_threads(listing)
    assert status['cores']==cores and spec['cores']==4
    profile=status.get('local_runtime',{})
    assert profile.get('cores',spec['cores'])==cores
    assert profile.get('sealed_cores',spec['cores'])==spec['cores'] and profile.get('mode','SMP')=='SMP'
    proof=profile.get('trial_sha256')
    if proof:
        decision=ROOT/'.runtime/receipts'/campaign/case/'local_core_trial.json'
        verified(decision,proof)
        trial=read(decision)
        assert trial['case']==CASE and trial['parent']==PARENT and trial['campaign']==campaign
        assert trial['mesh_sha256']==spec['case_mesh_sha256'] and spec['size_mm']==1.5
        assert trial['selected_cores']==cores==choose_cores(trial['matched_ramp_states'])
    else:
        assert cores==spec['cores']
    return dict(cores=cores,sealed_cores=spec['cores'],parallel_mode='SMP',timing_audit_sha256=proof)


def closed_clamp_reference(campaign):
    """A late pull rejection can still leave a closed and verified clamp history for the timing test."""
    receipt=ROOT/'.runtime/receipts'/campaign/PARENT
    if not (receipt/'released.txt').is_file():
        return False
    ledger=read(receipt/'archived.json')
    status=read(receipt/'status.json')
    spec=read(AUDIT/'local_core_trial_input.json')
    if ledger['case']!=PARENT or ledger['campaign']!=campaign or status['phase']!='solver_complete':
        return False
    folder=ROOT/'.runtime/archive'/campaign/PARENT
    hashes={f['name']:f['sha256'] for f in ledger['files']}
    if hashes.get('model.inp')!=spec['parent_input_sha256'] or status['cores']!=4:
        return False
    for name in ('pull.rst','pull.mntr','model.inp','solve.out'):
        verified(folder/name,hashes[name])
    checked=read(AUDIT/'clamp_core_readback_control.json')
    actual=monitor(folder/'pull.mntr')
    for row in checked['shared_native_sets']:
        i=row['substep']-1
        if i>=len(actual) or actual[i,3]!=row['cumulative_iterations'] or actual[i,4]!=row['load_time']:
            return False
    return checked['case']==PARENT and smp_threads((folder/'solve.out').read_text(errors='replace'))==4


def audit(case,campaign):
    spec=read(AUDIT/'local_core_trial_input.json')
    assert case==spec['case']==CASE
    runs=[];records=[]
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
        assert smp_threads(listing)==cores
        if name==CASE:
            assert status['exit']==0 and 'PB_CLAMP_SMP_TRIAL_COMPLETE' in listing
            assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',listing)
        raw=reader.read_binary(str(folder/(job+'.rst')))
        runs.append((raw,monitor(folder/(job+'.mntr')),folder/(job+'.rst'),name))
        records.append(dict(case=name,rst_sha256=sha[job+'.rst'],monitor_sha256=sha[job+'.mntr'],
                            input_sha256=expected,listing_sha256=sha['solve.out'],archive_sha256=digest(receipt/'archived.json')))
    sets=matched_stations(runs[0][1],runs[1][1])
    assert abs(runs[1][0].time_values[-1]-.4)<1e-8
    states=[]
    for (raw,history,path,name),entry in zip(runs,records,strict=True):
        fields=clamp_fields(raw,path,ROOT/'.runtime/post'/campaign/name/'clamp_core_fields',entry['rst_sha256'],sets)
        states.append((raw,fields,history))
        entry['DPF']={k:dict(nodes=len(v['ids']),files=v['files']) for k,v in fields.items()}
    compare=compare_states(*states,sets)
    first,last=compare[0],compare[-1]
    d4=last['four_core_elapsed_s']-first['four_core_elapsed_s']
    d12=last['twelve_core_elapsed_s']-first['twelve_core_elapsed_s']
    assert min(d4,d12)>0
    faster=choose_cores(compare)
    psha,pm=records[0]['rst_sha256'],records[0]['monitor_sha256']
    tsha,tm=records[1]['rst_sha256'],records[1]['monitor_sha256']
    write_json(AUDIT/'local_core_trial.json',dict(case=CASE,campaign=campaign,parent=PARENT,parent_rst_sha256=psha,
               trial_rst_sha256=tsha,parent_monitor_sha256=pm,trial_monitor_sha256=tm,matched_ramp_states=compare,
               verified_runs=records,mesh_sha256=spec['mesh_sha256'],trial_input_record_sha256=digest(AUDIT/'local_core_trial_input.json'),
               selected_cores=faster,
               warm_four_core_seconds=d4,warm_twelve_core_seconds=d12,warm_factor=d4/d12,
               scope='Wall time over identical accepted warm increments on the same physical host. The matrix includes '
                     'the full case and fixtures. The moving cell has not begun lateral contact in this control.'))


def readback_control():
    """Check full-field decoding on two published snapshots of the same four-core clamp."""
    from local_equilibrium import positions
    from tab_seating import read_point_file
    states=[];records=[];sets=[1,2,3,4]
    qa=ROOT/'.runtime/qa/snug125'
    for loc in ('ls3_ss12','ls3_ss24'):
        folder=qa/'forward-readback'/loc
        meta=read(folder/'capture.json')
        checkpoint=read(AUDIT/f'{PARENT}_{loc}_checkpoint.json')
        assert meta['case']==PARENT and meta['sha256']==checkpoint['rst_sha256']
        path=folder/'pull.rst'
        verified(path,meta['sha256'])
        raw=reader.read_binary(str(path))
        full=clamp_fields(raw,path,qa/'local-runtime'/loc,meta['sha256'],sets)
        request=read(folder/'dpf_points/request.json')
        scoped,_=read_point_file(path,folder/'dpf_points',meta['sha256'],request['sets'],request['nodes'])
        indices=positions(full['U']['ids'],request['nodes'])
        discrepancy=float(abs(scoped[:4]-full['U']['data'][:,indices]).max())
        assert discrepancy<1e-12
        states.append((raw,full,monitor(folder/'pull.mntr')))
        records.append(dict(checkpoint=loc,source_sha256=meta['sha256'],unit='mm and rad',
            verified_smp_cores=smp_threads((folder/'solve.out').read_text(errors='replace')),
            DPF_translation_nodes=len(full['U']['ids']),DPF_rotation_nodes=len(full['ROT']['ids']),
            independently_scoped_translation_nodes=len(indices),max_scoped_translation_difference_mm=discrepancy,
            original_subset_readback_sha256=digest(folder/'dpf_points/displacements.bin'),
            max_translation_mm=float(abs(full['U']['data']).max()),max_rotation_rad=float(abs(full['ROT']['data']).max())))
    rows=compare_states(*states,sets)
    for row in rows:
        del row['four_core_elapsed_s'],row['twelve_core_elapsed_s']
    write_json(AUDIT/'clamp_core_readback_control.json',dict(case=PARENT,
        scope='Two stationary RST captures of the same four-core parent, for full-field reader verification only.',
        physical_checks=records,shared_native_sets=rows))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('stage','audit','readback'));p.add_argument('--campaign',default='nov08_01')
    args=p.parse_args()
    if args.action=='stage':stage()
    elif args.action=='readback':readback_control()
    else:audit(CASE,args.campaign)

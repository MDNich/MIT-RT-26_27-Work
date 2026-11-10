"""Check the closed whole-shell pilot against its equilibrated fixture, signed inputs and native contact output."""
import re
import sys

import numpy as np

from audit_local import ROOT, read
from audit_snug_shell import surfaces, total_reaction
from film_identity import digest, verified, write_json
from global_contact import pair_summary
from native_rst import read_rst
from snug_shell_equilibrium import solid_parts
from stage_snug_fit import AUDIT


def pair_tracker(path):
    """Accept six named pair variables in their declared order and a monotone physical time column."""
    text=path.read_text(errors='replace')
    names=('pbfx','pbfy','pbfz','pbclosed','pbpress','pbpen')
    lower=text.lower()
    assert all(re.search(r'\b'+n+r'\b',lower) for n in names)
    first=[re.search(r'\b'+n+r'\b',lower).start() for n in names]
    assert first==sorted(first)
    rows=[]
    for line in text.splitlines():
        cols=line.strip().replace(',',' ').split()
        if len(cols)!=7:
            continue
        try:
            values=[float(v.replace('D','E')) for v in cols]
        except ValueError:
            continue
        rows.append(values)
    a=np.array(rows)
    assert a.ndim==2 and a.shape[1]==7 and len(a)>2
    assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
    return a


def displacements(raw,k,nodes):
    ids,u=raw.nodal_displacement(k)
    i=np.searchsorted(ids,nodes)
    assert np.array_equal(ids[i],nodes) and np.isfinite(u[i,:3]).all()
    return u[i,:3]


def audit(case,campaign):
    variant,kind=re.fullmatch(r'shellwave_(snug125_(?:nylon|aluminium))_(free|contact)_pilot_s4',case).groups()
    registry=AUDIT/(variant+'_shellwave_pilot_s4.json')
    spec=read(registry)[case]
    assert read(registry.with_name(registry.stem+'_preflight.json'))['registry_sha256']==digest(registry)
    rt=ROOT/'.runtime';folder=rt/'archive'/campaign/case;receipt=rt/'receipts'/campaign/case
    state=read(receipt/'status.json');ledger=read(receipt/'archived.json')
    assert spec['campaign']==campaign==ledger['campaign'] and ledger['case']==case==state['case']
    assert (receipt/'released.txt').is_file() and state['phase']=='solver_complete' and state['exit']==0
    hashes={r['name']:r['sha256'] for r in ledger['files']}
    for name,sha in spec['files'].items():
        assert hashes[name]==sha
        verified(folder/name,sha)
    for name in ('file.rst','solve.out'):
        verified(folder/name,hashes[name])
    listing=(folder/'solve.out').read_text(errors='replace')
    assert 'PB_SNUG_TRANSIENT_COMPLETE' in listing and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',listing)
    static=read(ROOT/'validation/shell_equilibrium'/(spec['static_fixture']+'.json'))
    assert static['case']==spec['static_fixture'] and static['campaign']==campaign and not static['review_flags']
    old_rst=rt/'archive'/campaign/spec['static_fixture']/'file.rst'
    verified(old_rst,static['rst_sha256'])
    old,raw=read_rst(old_rst),read_rst(folder/'file.rst')
    for et in (852,853):
        assert surfaces(old,et)==surfaces(raw,et)
    assert np.array_equal(raw.mesh.nnum,old.mesh.nnum) and np.array_equal(raw.mesh.nodes,old.mesh.nodes)
    parts=solid_parts(raw);reference_parts=solid_parts(old)
    assert parts.keys()==reference_parts.keys()
    for m,part in parts.items():
        assert all(np.array_equal(a,b) for a,b in zip(part,reference_parts[m],strict=True))
    cache=rt/'shell_fixture'/campaign/variant/'parent_fields.npz'
    verified(cache,spec['drive_field_sha256'])
    with np.load(cache) as parent:
        nodes=parent['nodes'];ports=parent['driven'];bearings=parent['bearing']
    groups={str(m):entries[3] for m,entries in parts.items() if m!=850}
    groups['bearing']=bearings
    start=spec['startup_time'];rate=spec['sample_rate_Hz'];last=spec['final_sample']
    t=np.asarray(raw.time_values);nlock=len(spec['preload_times'])
    expected_t=np.r_[spec['preload_times'],start,start+np.arange(4,last+1,4)/rate]
    assert np.allclose(t,expected_t,rtol=0,atol=5e-9)
    lock_set=nlock-1;rest_set=nlock
    original_lock=displacements(old,lock_set,nodes)
    checks=[]
    for k in (lock_set,rest_set):
        delta=displacements(raw,k,nodes)-original_lock
        checks.append(float(np.linalg.norm(delta,axis=1).max()))
    assert max(checks)<.3e-6
    full_times=np.r_[spec['preload_times'],start,start+np.asarray(spec['full_output_samples'])/rate]
    full=np.array([int(np.argmin(abs(t-v))) for v in full_times])
    assert np.max(abs(t[full]-full_times))<5e-9
    knots=np.loadtxt(folder/'pbt.dat');assert np.array_equal(ports,np.loadtxt(folder/'pbn.dat'))
    coef=np.loadtxt(folder/'pbq.dat').reshape(len(knots),-1,order='F')
    q=np.stack([np.interp(t[full],knots,col) for col in coef.T],axis=1)
    reference=np.stack([q@np.loadtxt(folder/('shape'+a+'.dat')).reshape(coef.shape[1],len(ports),order='F')
                        for a in 'xyz'],axis=2)
    errors=[float(np.linalg.norm(displacements(raw,k,ports)-ref,axis=1).max()) for k,ref in zip(full,reference,strict=True)]
    assert max(errors)<2e-8
    rf=[total_reaction(raw,k,groups) for k in range(len(t))]
    record=dict(case=case,campaign=campaign,registry_sha256=digest(registry),rst_sha256=hashes['file.rst'],
                static_fixture_rst_sha256=static['rst_sha256'],native_mcf_sha256=spec['native_mcf_sha256'],
                last_physical_time_s=last/rate,source_stride=spec['stride'],result_sets=len(t),
                largest_port_error_m=max(errors),locked_and_held_shell_errors_m=checks,
                result_file_bytes=(folder/'file.rst').stat().st_size,scope='Verification of the short native transient. '
                'The reported interval covers startup before the nominal outer-cell crossings.')
    if kind=='contact':
        verified(folder/'file.nlh',hashes['file.nlh'])
        tracker=pair_tracker(folder/'file.nlh')
        it=np.array([int(np.argmin(abs(tracker[:,0]-time))) for time in t[full]])
        assert np.max(abs(tracker[it,0]-t[full]))<5e-6
        state=tracker[tracker[:,0]>start+1e-7]
        assert len(state)>0 and np.max(np.diff(np.r_[start,state[:,0]]))<=spec['stride']/rate+5e-6
        ids=np.array(sorted(surfaces(raw,853).values()))
        values=[]
        for k in full:
            enum,results,labels=raw.element_solution_data(k,'ECT')
            row=pair_summary(k,t[k],ids,enum,results,labels)
            enum,results,_=raw.element_solution_data(k,'EMN')
            select=np.searchsorted(enum,ids);assert np.array_equal(enum[select],ids)
            force=np.zeros(3)
            for j in select:
                v=results[j]
                if v is not None and len(v):
                    assert len(v)>=45
                    force+=v[42:45]
            values.append(dict(time=float(t[k]),force_N=force.tolist(),closed_faces=row['sliding']+row['sticking']))
        native=np.array([v['force_N'] for v in values])
        assert np.linalg.norm(native)>1e-6
        sign=1 if np.sum(native*tracker[it,1:4])>0 else -1
        mismatch=np.linalg.norm(native-sign*tracker[it,1:4],axis=1)
        assert np.all(mismatch<.001+.003*np.linalg.norm(native,axis=1))
        assert np.all((tracker[it,4]>0)==np.array([v['closed_faces']>0 for v in values]))
        record.update(tracker_sha256=hashes['file.nlh'],tracker_force_sign_relative_to_RST=sign,
                      max_tracker_RST_force_difference_N=float(mismatch.max()),native_contact_samples=values,
                      tracked_dynamic_substeps=len(state))
    dynamic=np.flatnonzero(t>start+1e-8)
    substeps=raw._resultheader['ls_table'][dynamic,:2]
    record['dynamic_substeps']=substeps[:,1].tolist()
    if kind=='contact':
        free_name=case.replace('_contact_pilot_','_free_pilot_')
        free=read(ROOT/'validation/shellwave_pilot'/(free_name+'.json'))
        assert free['native_mcf_sha256']==record['native_mcf_sha256'] and free['registry_sha256']==record['registry_sha256']
        assert np.allclose(t,[r['time'] for r in free['reactions_N']],rtol=0,atol=5e-9)
        # Fully prescribed targets have identical velocities and accelerations for this matched
        # Newmark comparison only if both runs took the same internal steps from rest.
        sequence=np.arange(1,len(dynamic)+1)
        assert np.array_equal(free['dynamic_substeps'],sequence) and np.array_equal(substeps[:,1],sequence)
        hist=[]
        for k in range(rest_set,len(t)):
            other=free['reactions_N'][k]['groups']
            delta={m:rf[k][m]-other[m] for m in groups if m!='bearing'}
            sample=int(np.argmin(abs(tracker[:,0]-t[k])))
            assert abs(tracker[sample,0]-t[k])<5e-6
            target_sum=np.sum(list(delta.values()),axis=0)
            error=float(np.linalg.norm(target_sum+sign*tracker[sample,1:4]))
            assert error<.02+.003*np.linalg.norm(target_sum)
            hist.append(dict(time=float(t[k]),hardware_balance_residual_N=error,
                             prescribed_body_contact_reaction_N={m:v.tolist() for m,v in delta.items()}))
        record['matched_free_sha256']=free['rst_sha256']
        record['contact_transfer_check']=hist
    record['reactions_N']=[dict(time=float(time),groups={name:f.tolist() for name,f in row.items()})
                           for time,row in zip(t,rf,strict=True)]
    write_json(ROOT/'validation/shellwave_pilot'/(case+'.json'),record)
    print(case,len(t),'accepted pilot result sets')


if __name__=='__main__':
    audit(*sys.argv[1:])

"""Read physical-time force histories from a driven transient patch and audit their driving motion."""
import re,sys
import numpy as np
from audit_local import ROOT,read
from audit_contact_patch import native_field
from contact_patch import FS,integrate,local_fields
from film_identity import digest,verified,write_json
from native_rst import read_rst

def audit(case,campaign):
    rt=ROOT/'.runtime';d=rt/'archive'/campaign/case;receipt=rt/'receipts'/campaign/case
    spec=read(ROOT/'validation/contact_replay_inputs.json')[case]
    archive=read(receipt/'archived.json');status=read(receipt/'status.json')
    assert (receipt/'released.txt').is_file() and archive['case']==spec['case']==case and archive['campaign']==campaign==spec['campaign']
    assert status['phase']=='solver_complete' and status['exit']==0
    files={row['name']:row['sha256'] for row in archive['files']}
    for name,sha in spec['files'].items():
        assert files[name]==sha
        verified(d/name,sha)
    for name in ('file.rst','solve.out'):
        verified(d/name,files[name])
    log=(d/'solve.out').read_text(errors='replace')
    assert 'PB_TRANSIENT_COMPLETE' in log and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log)
    raw=read_rst(d/'file.rst')
    times=raw.time_values
    ls=raw._resultheader['ls_table'][:,:2]
    assert np.array_equal(ls,[(int(s),int(k)) for s,k in re.findall(r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED',log)])
    assert np.array_equal(np.unique(ls[:,0]),[1,2,3]) and abs(times[-1]-1-spec['last_physical_time_s'])<1e-8
    mask=ls[:,0]==3
    assert np.all(np.diff(times)>0) and np.max(np.diff(np.r_[1.,times[mask]]))<=spec['stride']/FS*1.0001
    state=local_fields(campaign,spec['radius_mm'])
    assert state['native_basis']==spec['global_basis_sha256'] and state['native_static']==spec['global_static_sha256']
    columns=raw.grid.cell_data;ids=columns['ansys_elem_num'][columns['ansys_etype']==3]
    contact=spec['kind']=='contact'
    assert len(ids)==(len(state['bodies'][850][1]) if contact else 0)
    cut=state['bodies'][850][2]
    cut_faces={int(e[8]) for e in raw.mesh.elem if e[1]==3 and np.intersect1d(cut,e[10:18]).size}
    cells=np.union1d(state['groups'][187],state['groups'][191])
    force=[];cell_rf=[];closed=[];cut_count=[];penetrations=[];checksets=[]
    for k in np.flatnonzero(mask):
        rf,at,dof=raw.nodal_reaction_forces(k)
        rc=np.zeros(3);pick=np.isin(at,cells)
        np.add.at(rc,dof[pick]-1,rf[pick]);cell_rf.append(rc)
        f=np.zeros(3);near_cut=0;num=0;pen=0.
        if contact:
            elem,records,_=raw.element_solution_data(k,'EMN')
            loc=np.searchsorted(elem,ids);assert np.array_equal(elem[loc],ids)
            for ident,slot in zip(ids,loc,strict=True):
                a=records[slot]
                if a is None or not len(a):continue
                assert len(a)>=45
                if a[40] in (2,3):
                    f+=a[42:45];num+=1;near_cut+=int(ident in cut_faces)
                    pen=max(pen,float(a[8:12][np.isin(a[:4],[2,3])].max(initial=0)))
        force.append(f);closed.append(num);cut_count.append(near_cut);penetrations.append(pen*1000)
    force=np.array(force);cell_rf=np.array(cell_rf);closed=np.array(closed);dynamic=np.flatnonzero(mask)
    elapsed=times[mask]-1
    if contact:
        assert np.any(closed) and closed[0]==0
        onset=int(np.flatnonzero(closed)[0]);peak=int(np.argmax(np.linalg.norm(force,axis=1)))
        checksets.extend(dynamic[[onset,peak]])
    checksets=np.unique(np.r_[dynamic[np.linspace(0,len(dynamic)-1,15).astype(int)],checksets]).astype(int)
    stride=spec['stride'];indices=np.arange(spec['samples'])*stride
    t,q,_=integrate(state['freq'],state['gamma'],'X',indices)
    drive=np.searchsorted(state['nodes'],state['driven'])
    free=np.searchsorted(state['nodes'],np.setdiff1d(state['groups'][850],state['driven']))
    differences=[]
    for k in checksets:
        when=times[k]-1
        coords=np.array([np.interp(when,t,column) for column in q.T])
        parent=state['locked']+state['phi']@coords
        diff=np.linalg.norm(native_field(raw,k,state['nodes'])-parent,axis=1)
        differences.append(dict(time_s=when,maximum_cut_or_cell_error_m=float(diff[drive].max()),
                                maximum_free_PLA_difference_m=float(diff[free].max())))
    assert max(r['maximum_cut_or_cell_error_m'] for r in differences)<2e-8
    save=rt/'post'/campaign/case;save.mkdir(exist_ok=True,parents=True)
    np.savez_compressed(save/'forces.npz',time_s=elapsed,contact_force_N=force,cell_drive_N=cell_rf,
                        closed_faces=closed,cut_faces=cut_count,penetration_mm=penetrations)
    rec=dict(case=case,campaign=campaign,states=len(elapsed),rst_sha256=files['file.rst'],
             waveform_duration_s=float(elapsed[-1]),sampled_motion_checks=differences,
             peak_net_contact_N=float(np.linalg.norm(force,axis=1).max()),contact_impulse_Ns=np.trapezoid(force,elapsed,axis=0).tolist(),
             max_loaded_penetration_mm=float(max(penetrations)),peak_loaded_cut_edge_faces=max(cut_count),
             force_history_sha256=digest(save/'forces.npz'),scope=spec['scope'])
    if contact:
        rec.update(first_closed_bracket_s=elapsed[[max(0,onset-1),onset]].tolist(),peak_force_time_s=float(elapsed[peak]))
    write_json(ROOT/'validation/contact_replay'/f'{case}.json',rec)
    print(case,len(elapsed),'transient equilibria')
if __name__=='__main__':audit(*sys.argv[1:])

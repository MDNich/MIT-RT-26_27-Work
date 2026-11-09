"""Verify native whole-shell equilibrium, applied motions and force transfer by target body."""
import re
import sys

import numpy as np

from audit_local import ROOT,read
from case_stress import source
from film_identity import verified,write_json
from global_contact import pair_summary
from native_rst import read_rst
from snug_shell_equilibrium import solid_parts
from stage_snug_fit import AUDIT


def surfaces(result,kind):
    grid=result.grid.cell_data
    elements=np.sort(grid['ansys_elem_num'][grid['ansys_etype']==kind])
    order=np.argsort(result.mesh.enum)
    i=order[np.searchsorted(result.mesh.enum[order],elements)]
    assert np.array_equal(result.mesh.enum[i],elements)
    faces={}
    for eid,j in zip(elements,i,strict=True):
        row=result.mesh.elem[j][10:18]
        assert len(row)==8
        if row[2]==row[3]:
            assert row[6]==row[2]
            corners=row[:3];edges=row[[4,5,7]]
        else:
            corners=row[:4];edges=row[4:]
        # Preserve face direction while allowing cyclic renumbering.
        shift=-int(corners.argmin())
        key=tuple(np.r_[np.roll(corners,shift),np.roll(edges,shift)].tolist())
        assert key not in faces
        faces[key]=int(eid)
    return faces


def total_reaction(result,k,groups):
    values,ids,dof=result.nodal_reaction_forces(k)
    assert np.isfinite(values).all() and np.all(np.isin(dof,[1,2,3]))
    totals={};assigned=np.zeros(len(ids),dtype=bool)
    for label,nodes in groups.items():
        pick=np.isin(ids,nodes)
        assert not np.any(assigned & pick)
        totals[label]=np.bincount(dof[pick]-1,weights=values[pick],minlength=3)
        assigned|=pick
    assert np.max(abs(values[~assigned]),initial=0.)<1.e-7
    return totals


def audit(case,campaign):
    variant=case.removeprefix('shell_').rsplit('_',2)[0]
    spec=read(AUDIT/(variant+'_shell_inputs_v2.json'))[case]
    rt=ROOT/'.runtime';receipt=rt/'receipts'/campaign/case;archive=rt/'archive'/campaign/case
    state=read(receipt/'status.json');ledger=read(receipt/'archived.json')
    assert spec['campaign']==ledger['campaign']==campaign and spec['case']==state['case']==ledger['case']==case
    assert state['phase']=='solver_complete' and state['exit']==0 and (receipt/'released.txt').is_file()
    checksums={row['name']:row['sha256'] for row in ledger['files']}
    for name,sha in spec['files'].items():
        assert checksums[name]==sha;verified(archive/name,sha)
    for name in ('file.rst','solve.out'):verified(archive/name,checksums[name])
    listing=(archive/'solve.out').read_text(errors='replace')
    assert 'PB_SHELL_PATH_COMPLETE' in listing and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',listing)
    raw=read_rst(archive/'file.rst');parts=solid_parts(raw)
    parent,_,original=source(spec['static_case'],campaign)
    assert parent['rst_sha256']==spec['static_rst_sha256']
    ref_parts=solid_parts(original)
    for mat,(et,es,conn,ids) in parts.items():
        te,re,rc,rn=ref_parts[mat]
        assert et==te and np.array_equal(es,re) and np.array_equal(conn,rc) and np.array_equal(ids,rn)
    contact=spec['contact']
    faces=surfaces(raw,853);targets=surfaces(raw,852)
    provenance=read(AUDIT/(spec['static_case']+'_contacts.json'))
    assert provenance['rst_sha256']==parent['rst_sha256']
    if contact:
        for et in [852,853]:
            ref=original.grid.cell_data;candidate=raw.grid.cell_data
            assert np.array_equal(np.unique(ref['ansys_material_type'][ref['ansys_etype']==et]),
                                  np.unique(candidate['ansys_material_type'][candidate['ansys_etype']==et]))
        old=surfaces(original,853)
        assert faces.keys()==old.keys() and targets.keys()==surfaces(original,852).keys()
        global_ids={new:old[key] for key,new in faces.items()}
    else:assert not faces and not targets
    cache=rt/'shell_fixture'/campaign/variant/'parent_fields.npz';verified(cache,spec['drive_field_sha256'])
    flags=[];history=[]
    with np.load(cache) as data:
        nodes=data['nodes'];drive=data['driven'];bearing=data['bearing'];t=data['t'][1:];reference=data['u'][1:]
        assert np.array_equal(raw.mesh.nnum,nodes)
        assert np.allclose(raw.time_values,t,rtol=0,atol=1.e-9)
        assert np.array_equal(raw._resultheader['ls_table'][:,0],np.arange(1,len(t)+1))
        base_idx=np.searchsorted(original.mesh.nnum,nodes)
        assert np.max(abs(raw.mesh.nodes-original.mesh.nodes[base_idx]))<1.e-10
        groups={str(mat):v[3] for mat,v in parts.items() if mat!=850};groups['bearing']=bearing
        driven=np.searchsorted(nodes,drive);shell=np.searchsorted(nodes,parts[850][3])
        contact_ids=np.array(sorted(faces.values()),int)
        for k,time in enumerate(t):
            nums,u=raw.nodal_displacement(k);ix=np.searchsorted(nums,nodes)
            assert np.array_equal(nums[ix],nodes)
            u=u[ix,:3];assert np.isfinite(u).all()
            error=np.linalg.norm(u-reference[k],axis=1)
            assert error[driven].max()<2.e-8
            totals=total_reaction(raw,k,groups)
            balance=np.linalg.norm(sum(totals.values()))
            scale=sum(np.linalg.norm(x) for x in totals.values())
            if balance>.02+.001*scale:flags.append((k+1,'global force balance',float(balance)))
            result=dict(set=k+1,load_parameter=float(time),maximum_drive_error_um=float(1e6*error[driven].max()),
                       maximum_PLA_difference_from_parent_um=float(1e6*error[shell].max()),
                       reaction_N={m:f.tolist() for m,f in totals.items()},balance_residual_N=float(balance))
            if contact:
                en,ect,labels=raw.element_solution_data(k,'ECT')
                summary=pair_summary(k,float(time),contact_ids,en,ect,labels)
                ei,misc,_=raw.element_solution_data(k,'EMN')
                ii=np.searchsorted(ei,contact_ids);assert np.array_equal(ei[ii],contact_ids)
                force=np.zeros(3)
                for idx in ii:
                    vals=misc[idx]
                    if vals is not None and len(vals):
                        assert len(vals)>=45
                        force+=vals[42:45]
                residual=np.linalg.norm(force-totals['bearing'])
                if residual>.02+.003*np.linalg.norm(force):flags.append((k+1,'interface force balance',float(residual)))
                result.update(contact_state=summary,contact_resultant_N=force.tolist(),
                              contact_reaction_residual_N=float(residual))
                if k<8 or k==len(t)-1:
                    parent_k=min(k,7)
                    original_loaded={e for f in provenance['contact_history'][parent_k]['loaded_case_faces'] for e in f['element_ids']}
                    indices=np.searchsorted(en,contact_ids)
                    loaded={global_ids[int(e)] for e,record in zip(contact_ids,indices,strict=True)
                            if ect[record] is not None and len(ect[record]) and
                            np.max(ect[record][:10*len(labels[record]):10])>=2}
                    result.update(parent_closed_faces=sorted(original_loaded),replay_closed_faces_mapped_to_parent=sorted(loaded))
                    if k in (7,len(t)-1) and not loaded.intersection(original_loaded):
                        flags.append((k+1,'installed patch was not recovered',len(loaded)))
                    if error[shell].max()>.3e-6:
                        flags.append((k+1,'installed shell displacement differs by more than 0.30 micrometres',float(error[shell].max()*1e6)))
            else:
                max_rf=max(np.linalg.norm(v) for m,v in totals.items() if m!='bearing')
                if max_rf>.02:flags.append((k+1,'free hardware resultant',float(max_rf)))
            history.append(result)
    rec=dict(case=case,variant=variant,campaign=campaign,rst_sha256=checksums['file.rst'],
             input_sha256=checksums['model.inp'],static_rst_sha256=spec['static_rst_sha256'],
             driven_nodes=len(drive),verified_target_faces=len(targets),verified_case_faces=len(faces),
             history=history,review_flags=flags,scope=spec['scope'])
    destination='review_shell_equilibrium' if flags else 'shell_equilibrium'
    write_json(ROOT/'validation'/destination/(case+'.json'),rec)
    print(case,len(history),'stations',destination,flags[:3])


if __name__=='__main__':audit(*sys.argv[1:])

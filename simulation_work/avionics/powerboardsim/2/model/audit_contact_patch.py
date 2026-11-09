"""Check native reaction balance and local deformation against the imposed board motion."""
import re
import sys

import numpy as np
import pyvista as pv

from audit_local import ROOT,read
from contact_patch import local_fields
from film_identity import verified,write_json
from native_rst import read_rst


def native_field(result,index,nodes):
    n,u=result.nodal_displacement(index)
    order=np.argsort(n)
    rows=order[np.searchsorted(n[order],nodes)]
    assert np.array_equal(n[rows],nodes)
    displacement=u[rows,:3]
    assert np.isfinite(displacement).all()
    return displacement


def exterior(state,materials,displacement):
    nodes=state['nodes']
    xyz=state['xyz']+displacement
    skin=[]
    for mat in materials:
        side=np.array([n for _,n in state['bodies'][mat][1]])
        side=np.searchsorted(nodes,side)
        for triangle in ((0,3,5),(3,1,4),(5,4,2),(3,4,5)):
            skin.extend(side[:,triangle])
    skin=np.asarray(skin)
    return pv.PolyData(xyz,np.column_stack((np.full(len(skin),3),skin)).ravel())


def audit(case,campaign):
    snug = case.startswith('patch_snug125_')
    if snug:
        variant=case.removeprefix('patch_').split('_Z_span')[0]
        spec=read(ROOT/'validation/snug125'/(variant+'_patch_inputs.json'))[case]
    else:
        spec=read(ROOT/'validation/contact_patch_inputs.json')[case]
    assert spec['case']==case and spec['campaign']==campaign
    rt=ROOT/'.runtime'
    d=rt/'archive'/campaign/case
    receipt=rt/'receipts'/campaign/case
    meta=read(receipt/'archived.json')
    status=read(receipt/'status.json')
    assert (receipt/'released.txt').is_file() and status['exit']==0 and status['phase']=='solver_complete'
    files={row['name']:row['sha256'] for row in meta['files']}
    assert files['model.inp']==spec['input_sha256']==status['input_sha256'].lower()
    for name in ('model.inp','solve.out','file.rst'):
        verified(d/name,files[name])
    listing=(d/'solve.out').read_text(errors='replace')
    assert 'LOCAL_CUT_PATH_COMPLETED' in listing and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',listing)
    assert not re.search(r'(ESURF|constraint).{0,80}(ignored|skipped)',listing,re.I)
    if snug:
        verified(ROOT/'validation/snug125'/(variant+'_seeded_contact.json'),spec['parent_sample_audit_sha256'])
        from snug_contact_patch import fields
        state=fields(variant,campaign,spec['radius_mm'])
    else:
        state=local_fields(campaign,spec['radius_mm'])
    assert state['native_static']==spec['parent_static_sha256'] and state['native_basis']==spec['parent_modal_sha256']
    result=read_rst(d/'file.rst')
    steps=result._resultheader['ls_table'][:,:2]
    done=[tuple(map(int,v)) for v in re.findall(r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED',listing)]
    assert np.array_equal(steps,done)
    times=result.time_values
    assert np.all(np.diff(times)>0) and np.array_equal(np.unique(steps[:,0]),[1,2,3]) and times[-1]==3.
    nodes=state['nodes']
    driven=np.searchsorted(nodes,state['driven'])
    cut=state['bodies'][850][2]
    pla=state['groups'][850]
    free_pla=np.setdiff1d(pla,cut)
    cell_materials=sorted(m for m in state['groups'] if m!=850)
    cells=np.unique(np.concatenate([state['groups'][m] for m in cell_materials]))
    header=result.grid.cell_data
    contacts=header['ansys_elem_num'][header['ansys_etype']==3]
    targets=header['ansys_elem_num'][header['ansys_etype']==2]
    expected_faces=len(state['bodies'][850][1]) if spec['contact'] else 0
    assert len(contacts)==expected_faces
    assert len(targets)==(sum(len(state['bodies'][m][1]) for m in cell_materials) if spec['contact'] else 0)
    edges=set(cut.tolist())
    contact_edges=set()
    for elem in result.mesh.elem:
        if elem[1]==3 and edges.intersection(elem[10:18]):
            contact_edges.add(int(elem[8]))
    series=[]
    checks={}
    flags=[]
    for k,t in enumerate(times):
        values,ids,components=result.nodal_reaction_forces(k)
        assert np.all(np.isin(components,[1,2,3]))
        total=np.zeros((2,3))
        for i,group in enumerate([cells,cut]):
            take=np.isin(ids,group)
            np.add.at(total[i],components[take]-1,values[take])
        assert np.abs(values[~np.isin(ids,state['driven'])]).sum()<1e-8
        residual=np.linalg.norm(total.sum(axis=0))
        if residual >= .03 + .003*np.linalg.norm(total[0]):
            flags.append(dict(set=k+1,time=float(t),check='net external force',residual_N=float(residual)))
        row=dict(time=float(t),cells_reaction_N=total[0].tolist(),PLA_cut_reaction_N=total[1].tolist(),imbalance_N=float(residual))
        if snug:
            per_cell={}
            for material in cell_materials:
                take=np.isin(ids,state['groups'][material])
                reaction=np.zeros(3)
                np.add.at(reaction,components[take]-1,values[take])
                per_cell[str(material)]=reaction.tolist()
            assert np.allclose(np.sum(list(per_cell.values()),axis=0),total[0],rtol=1e-6,atol=1e-5)
            row['prescribed_cell_reactions_N']=per_cell
        if spec['contact']:
            enum,records,_=result.element_solution_data(k,'EMN')
            loc=np.searchsorted(enum,contacts)
            assert np.array_equal(enum[loc],contacts)
            loaded=[]
            for eid,i in zip(contacts,loc,strict=True):
                val=records[i]
                if val is None or len(val)==0:
                    continue
                assert len(val)>=45
                if val[40] in (2,3):
                    loaded.append((int(eid),val))
            forces=np.array([r[42:45] for _,r in loaded]).reshape(-1,3)
            contact=forces.sum(axis=0)
            mismatch=float(np.linalg.norm(total[1]-contact))
            if mismatch>=.04+.004*np.linalg.norm(contact):
                flags.append(dict(set=k+1,time=float(t),check='cut reactions versus contact resultant',residual_N=mismatch))
            pen=max((float(v[8:12][np.isin(v[:4],[2,3])].max(initial=0)) for _,v in loaded),default=0.)
            row.update(closed_faces=len(loaded),loaded_cut_edge_faces=sum(e in contact_edges for e,_ in loaded),
                       maximum_loaded_corner_penetration_mm=1000*pen,contact_sum_N=contact.tolist())
        if np.any(abs(np.array([1.,2.,3.])-t)<1e-8):
            u=native_field(result,k,nodes)
            scale=1. if abs(t-2)<1e-8 else 0.
            expected=state['locked']+scale*state['amplitude']
            diff=np.linalg.norm(u-expected,axis=1)
            assert max(diff[driven])<2e-8
            surfaces=[exterior(state,group,u) for group in [[850],cell_materials]]
            _,count=surfaces[0].collision(surfaces[1],box_tolerance=0.,cell_tolerance=0.)
            checks[str(round(t))]=dict(max_free_PLA_departure_from_parent_um=float(1e6*max(diff[np.searchsorted(nodes,free_pla)])),
                                      max_drive_difference_um=float(1e6*max(diff[driven])),intersecting_triangle_pairs=int(count))
        series.append(row)
    if spec['contact']:
        if snug:
            # The neighbouring middle pocket carries load at global lock. Check cyclic return at the same load.
            ends=[next(r for r in series if abs(r['time']-t)<1e-8) for t in (1.,3.)]
            repeat=float(np.linalg.norm(np.subtract(ends[0]['contact_sum_N'],ends[1]['contact_sum_N'])))
            if repeat>.04+.004*np.linalg.norm(ends[0]['contact_sum_N']):
                flags.append(dict(check='locked return resultant',residual_N=repeat))
            if any(r['loaded_cut_edge_faces'] for r in series):
                flags.append(dict(check='active contact reaches the artificial cut'))
        else:
            assert series[0]['closed_faces']==series[-1]['closed_faces']==0
            assert any(r['closed_faces']>0 for r in series if r['time']>1)
    else:
        assert max(np.linalg.norm(r['cells_reaction_N']) for r in series)<.02
    rec=dict(**spec,rst_sha256=files['file.rst'],equilibria=len(series),endpoint_checks=checks,force_history=series,
             scope='Nonlinear quasistatic response conditional on the prescribed boundary and cell motion at the selected waveform sample. Compare both domain sizes, contact state at the artificial cut, and free displacement recovery before using the force.')
    if flags:
        rec['classification']='Reaction checks failed. Result retained for numerical diagnosis.'
        rec['failed_checks']=flags
        write_json(ROOT/'validation/review_contact_patch'/f'{case}.json',rec)
        print(case,len(flags),'reaction checks failed')
        return
    write_json(ROOT/'validation/contact_patch'/f'{case}.json',rec)
    print(case,len(series),'native equilibria verified')
if __name__=='__main__':
    audit(*sys.argv[1:])

"""Identify the cell, strip and washer clearances in a partial full-board flush installation."""
import argparse
from pathlib import Path

import numpy as np
import pyvista as pv

from audit_local import ROOT,read
from curved_cell_contact import set_coordinates,curved_skins
from extend_board import FACE_MATERIALS
from film_identity import verified,write_json,digest
from native_rst import read_rst
from partition_tab_gap import check_geometry,export


def target_connectivity(rst):
    g=rst.grid.cell_data
    ids=g['ansys_elem_num'][(g['ansys_etype']==852)&(g['ansys_real_constant']==853)]
    order=np.argsort(rst.mesh.enum)
    elem=rst.mesh.elem
    ix=order[np.searchsorted(rst.mesh.enum[order],ids)]
    assert np.array_equal(rst.mesh.enum[ix],ids)
    return {int(num):tuple(map(int,elem[i][10:])) for num,i in zip(ids,ix,strict=True)}


def native_target_faces(ref, solids, folder, manifest):
    rows=target_connectivity(ref)
    combined={}
    for i in range(manifest['cores']):
        target=target_connectivity(read_rst(folder/f'file{i}.rst'))
        assert not set(combined).intersection(target)
        combined.update(target)
    assert len(combined)==len(rows)==9466 and sorted(rows.values())==sorted(combined.values())
    owner={}
    for m,solid in zip(FACE_MATERIALS,solids,strict=True):
        n=solid.point_data['ansys_node_num']
        assert not any(v in owner for v in n)
        owner.update((int(v),m) for v in n)
    faces={m:[] for m in FACE_MATERIALS}
    for face in combined.values():
        assert len(face)==8
        mat=owner[face[0]]
        assert all(owner[n]==mat for n in face)
        # MAPDL repeats the third corner in the fourth corner slot and the seventh
        # slot for the collapsed quadratic triangle.
        if face[2]==face[3]:
            assert face[6]==face[2]
            face=tuple(face[i] for i in (0,1,2,4,5,7))
        assert len(set(face))==len(face)
        faces[mat].append(face)
    output=[]
    for m,group in faces.items():
        nodes=np.unique(np.concatenate(group))
        conn=np.concatenate([np.r_[len(face),np.searchsorted(nodes,face)] for face in group])
        types=np.array([pv.CellType.QUADRATIC_TRIANGLE if len(face)==6 else pv.CellType.QUADRATIC_QUAD for face in group])
        grid=pv.UnstructuredGrid(conn,types,ref.mesh.nodes[np.searchsorted(ref.mesh.nnum,nodes)])
        grid.point_data['ansys_node_num']=nodes
        output.append(grid)
    return output


def run(folder):
    folder=folder.resolve()
    m=read(folder/'receipts.json')
    case,camp=m['case'],m['campaign']
    assert folder.parent.name==case and folder.parent.parent.name==camp
    mesh_case='stand3_nylon_static' if 'nylon' in case else 'stand3_aluminium_static'
    proof=read(ROOT/'validation/global'/(mesh_case+'.json'))
    mesh_path=ROOT/'.runtime/archive'/camp/mesh_case/'file.rst'
    verified(mesh_path,proof['rst_sha256'])
    ref=read_rst(mesh_path)
    grid=ref.quadgrid
    materials=[850,*FACE_MATERIALS]
    sel=np.isin(grid.cell_data['ansys_elem_type_num'],[185,186,187])
    solids=[grid.extract_cells(sel & (grid.cell_data['ansys_material_type']==v)) for v in materials]
    ids,count=check_geometry(ref,solids,folder,m)
    assert all(s.n_cells>0 for s in solids)
    reference=ref.mesh.nodes[np.searchsorted(ref.mesh.nnum,ids)]
    target_faces=native_target_faces(ref,solids[1:],folder,m)
    surfaces=[solids[0],*target_faces]
    history_file=ROOT/'validation/partition_checks'/case/(folder.name+'_history.json')
    history=read(history_file)['history']
    # Examine the last preload, the first loaded hardware contact, first board seat and the snapshot endpoint.
    sets={m['sets'],max(r['native_set'] for r in history if r['loadstep']==2)}
    for pair in ('853','880'):
        closed=[r['native_set'] for r in history if r['contact'][pair]['sliding']+r['contact'][pair]['sticking']>0]
        if closed:sets.add(closed[0])
    sets=sorted(sets)
    fields,sha=export(folder,m,ids,sets,folder.name+'_hardware')
    records={}
    for k,motion in zip(sets,fields,strict=True):
        set_coordinates(surfaces,ids,reference+motion)
        levels={}
        for level in (1,2,3):
            case_skin=curved_skins(surfaces[:1],level)[0]
            group={}
            for material,target in zip(materials[1:],target_faces,strict=True):
                skin=target.extract_surface(nonlinear_subdivision=level,algorithm='dataset_surface').triangulate()
                skin.points=skin.point_data['coordinates']
                assert skin.n_cells>0 and skin.n_open_edges==0
                _,pairs=case_skin.collision(skin,contact_mode=1,box_tolerance=0.,cell_tolerance=0.)
                distance=skin.compute_implicit_distance(case_skin).point_data['implicit_distance']*1000
                assert np.isfinite(distance).all()
                ix=int(np.argmin(distance))
                group[material]=dict(native_target_faces=target.n_cells,open_edges=skin.n_open_edges,intersect=bool(pairs),minimum_signed_vertex_gap_mm=float(distance[ix]),
                                     location_mm=(skin.points[ix]*1000).tolist())
            levels[level]=group
        records[k]=dict(travel_mm=history[k-1]['travel_mm'],levels=levels)
        print(k,[(v,round(d['minimum_signed_vertex_gap_mm'],4)) for v,d in levels[3].items() if v in (176,187,191) or d['intersect']],flush=True)
    out=ROOT/'validation/partition_checks'/case/(folder.name+'_hardware.json')
    write_json(out,dict(case=case,campaign=camp,checkpoint_sha256=digest(folder/'receipts.json'),DPF_sha256=sha,
        history_sha256=digest(history_file),geometry_control_sha256=proof['rst_sha256'],checked_elements=count,
        checked_nodes=len(ids),sets=records,cells=[176,187,191],outer_washers=[178,181,182,183],
        nickel=[174,179,180,186,189,193],scope='Closed PLA skin and the 9,466 native hardware target facets at the listed converged states. Signed distance '
        'samples target vertices against the printed material. Triangle intersection is a separate geometric test. '
        'Post-scope elastic displacements do not establish hardware load capacity.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('checkpoint',type=Path)
    run(p.parse_args().checkpoint)

"""Locate load-carrying case faces and check the final cell and washer surfaces using native displacements."""
import argparse
from collections import Counter

import numpy as np
import gmsh
from vtkmodules.vtkCommonCore import vtkDoubleArray
from vtkmodules.vtkFiltersCore import vtkImplicitPolyDataDistance
from vtkmodules.util.numpy_support import vtk_to_numpy

from audit_local import ROOT, read, table
from curved_cell_contact import set_coordinates, curved_skins
from dpf_readback import export
from extend_board import NODE
from film_identity import digest, verified, write_json
from global_contact import pair_summary
from installed_cell_gap import target_connectivity, hardware_face_grids
from native_rst import read_rst
from stage_snug_fit import AUDIT, MESH, STEP, input_record


def surface_owners(rst, mesh_file, node_start=NODE):
    with np.load(mesh_file) as mesh:
        face_by_nodes = {tuple(sorted(tri+node_start)): int(key)
                         for key in mesh if key.isdigit() for tri in mesh[key]}
        expected = sum(len(mesh[k]) for k in mesh if k.isdigit())
    rows = [e for e in rst.mesh.elem if e[1]==853]
    assert len(face_by_nodes)==expected==len(rows)
    owners = {}
    for elem in rows:
        tri = elem[10:18]
        assert tri[2]==tri[3]==tri[6]
        key = tuple(sorted(tri[[0,1,2,4,5,7]]))
        owners[int(elem[8])] = face_by_nodes.pop(key)
    assert not face_by_nodes
    return owners


def contact_by_face(rst, owners, recorded):
    all_faces = np.array(sorted(owners))
    final = []
    for k, state in enumerate(recorded):
        enum, data, nodes = rst.element_solution_data(k,'ECT')
        pos = np.searchsorted(enum,all_faces)
        assert np.array_equal(enum[pos],all_faces)
        loaded = {}
        for element,i in zip(all_faces,pos,strict=True):
            vals = data[i]
            if vals is None or not len(vals):
                continue
            count = len(nodes[i])
            # pair_summary also checks record length, optional trailer and each native corner status.
            if vals[:count*10:10].max()>=2:
                loaded.setdefault(owners[element],[]).append(int(element))
        assert sum(map(len,loaded.values()))==state['sliding']+state['sticking']
        groups = []
        for face, ids in sorted(loaded.items()):
            summary=pair_summary(k,rst.time_values[k],np.array(ids),enum,data,nodes)
            groups.append(dict(STEP_face=face,closed_faces=len(ids),element_ids=ids,
                               max_pressure_MPa=summary['p_max']*1e-6,
                               max_loaded_penetration_mm=summary['loaded_corner_pen_max']*1000))
        peak=max((row['max_pressure_MPa'] for row in groups), default=0.)
        assert np.isclose(peak, state['p_max']*1e-6, atol=1.e-6)
        final.append(dict(native_set=k+1,loadstep=int(rst._resultheader['ls_table'][k,0]),
                          load_time=state['time_s'],loaded_case_faces=groups))
    return final


def loaded_face_geometry(history):
    tags=sorted({entry['STEP_face'] for state in history for entry in state['loaded_case_faces']})
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal',0)
        occ=gmsh.model.occ
        solid,=occ.importShapes(str(STEP));assert solid[0]==3
        occ.synchronize()
        return {tag:dict(surface_type=gmsh.model.getType(2,tag),area_mm2=occ.getMass(2,tag),
                         CAD_centre_of_area_mm=list(occ.getCenterOfMass(2,tag)),
                         CAD_bounds_mm=list(occ.getBoundingBox(2,tag))) for tag in tags}
    finally:
        gmsh.finalize()


def contact_parts(rst):
    bodies = read(ROOT/'validation/rigid_case_drawdown.json')['records']
    mapping = {r['STEP_body']:r['native_material'] for r in bodies}
    target_ids = [4,19,15,1,6,9,10,11,20]
    materials = [850,*[mapping[n] for n in target_ids]]
    g = rst.quadgrid
    solid = np.isin(g.cell_data['ansys_elem_type_num'],[185,186,187])
    parts = [g.extract_cells(solid & (g.cell_data['ansys_material_type']==m)) for m in materials]
    faces=target_connectivity(rst)
    assert len(faces)==9466 and len(set(faces.values()))==len(faces)
    parts=[parts[0],*hardware_face_grids(rst,materials[1:],parts[1:],faces.values())]
    return parts, [(body,mapping[body]) for body in target_ids]


def sampled_gaps(parts, targets_by_body):
    rows=[]
    for level in (2,3):
        cap, *targets=curved_skins(parts,level)
        distance=vtkImplicitPolyDataDistance()
        distance.SetInput(cap)
        for (body,material),target in zip(targets_by_body,targets,strict=True):
            _,n=cap.collision(target,contact_mode=1,box_tolerance=0.,cell_tolerance=0.)
            output=vtkDoubleArray()
            distance.FunctionValue(target.GetPoints().GetData(),output)
            val=vtk_to_numpy(output)*1000
            assert len(val)==target.n_points and np.isfinite(val).all()
            rows.append(dict(subdivision=level,body=body,material=material,intersects=bool(n),
                             minimum_signed_target_vertex_gap_mm=float(val.min())))
    return rows


def locked_geometry(rst, case, campaign):
    parts, targets = contact_parts(rst)
    ids = np.unique(np.concatenate([p.point_data['ansys_node_num'] for p in parts]))
    k = rst.nsets
    suffix = export(case,campaign,[k])/f'set_{k:04d}'
    numbers=np.fromfile(suffix.with_suffix('.ids'),'<i4')
    disp=np.fromfile(suffix.with_suffix('.u'),'<f8').reshape(-1,3)
    order=np.argsort(numbers)
    j=order[np.searchsorted(numbers[order],ids)]
    i=np.searchsorted(rst.mesh.nnum,ids)
    assert np.array_equal(numbers[j],ids) and np.array_equal(rst.mesh.nnum[i],ids)
    set_coordinates(parts,ids,rst.mesh.nodes[i]+disp[j])
    rows = sampled_gaps(parts, targets)
    return dict(displacement_sha256=digest(suffix.with_suffix('.u')),node_ids_sha256=digest(suffix.with_suffix('.ids')),
                native_set=k,rows=rows)


def check_resultant(rst,owners,archive,history):
    native=table(archive/'snug_contact_force.csv')
    assert len(native)==rst.nsets and np.array_equal(native['native_set'],np.arange(rst.nsets)+1)
    assert np.allclose(native['load_time'],rst.time_values,rtol=0,atol=1e-8)
    faces=np.array(sorted(owners))
    rows=[]
    for k,(station,state) in enumerate(zip(native,history,strict=True)):
        assert station['faces']==len(faces)
        ids,records,_=rst.element_solution_data(k,'EMN')
        inds=np.searchsorted(ids,faces);assert np.array_equal(ids[inds],faces)
        result=np.zeros((len(faces),3))
        for j,ind in enumerate(inds):
            values=records[ind]
            if values is not None and len(values):
                assert len(values)>=45
                result[j]=values[42:45]
        total=result.sum(axis=0)
        post=np.array([station[n] for n in ('fx_N','fy_N','fz_N')])
        assert np.isfinite(result).all() and np.allclose(total,post,rtol=2e-5,atol=1e-5)
        # Preserve cancellations when opposite surface normals are present.
        norms=np.linalg.norm(result,axis=1)
        if state['loaded_case_faces']:assert norms.max()>0
        rows.append(dict(native_set=k+1,force_xyz_N=post.tolist(),resultant_N=float(np.linalg.norm(total)),
                         sum_of_element_force_magnitudes_N=float(norms.sum()),
                         maximum_POST1_difference_N=float(np.max(np.abs(total-post)))))
    return rows


def run(case,campaign):
    registered=input_record(case)
    verified(STEP,registered['step_sha256'])
    mesh=MESH/f"case_{registered['size_mm']}.npz";verified(mesh,registered['mesh_sha256'])
    parent=read(AUDIT/f'{case}_installed.json')
    assert parent['case']==case and parent['campaign']==campaign
    path=ROOT/'.runtime/archive'/campaign/case/'file.rst';verified(path,parent['rst_sha256'])
    rst=read_rst(path)
    owners=surface_owners(rst,mesh,registered.get('case_node_start',NODE))
    history=contact_by_face(rst,owners,parent['contact_history'])
    results=dict(case=case,campaign=campaign,rst_sha256=parent['rst_sha256'],step_sha256=registered['step_sha256'],
                 case_mesh_sha256=registered['mesh_sha256'],number_of_contact_faces_by_STEP_face=dict(Counter(owners.values())),
                 loaded_STEP_face_geometry=loaded_face_geometry(history),contact_history=history,locked_geometry=locked_geometry(rst,case,campaign),
                 scope='Stored native contact corners grouped by exact case-mesh connectivity. Triangle intersection and signed target-vertex distances use the deformed quadratic case exterior and native hardware target faces at two subdivisions; vertex samples can miss face-to-face contact.')
    if registered.get('extra_output'):
        results['resultant_force_check']=check_resultant(rst,owners,path.parent,history)
        results['native_force_csv_sha256']=digest(path.parent/'snug_contact_force.csv')
    write_json(AUDIT/f'{case}_contacts.json',results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case');parser.add_argument('--campaign',default='nov08_01')
    args=parser.parse_args();run(args.case,args.campaign)

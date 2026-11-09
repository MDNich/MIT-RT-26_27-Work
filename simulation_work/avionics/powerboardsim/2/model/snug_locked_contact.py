"""Locate load-carrying case faces and check the final cell and washer surfaces using native displacements."""
import argparse
from collections import Counter

import numpy as np
import gmsh
from vtkmodules.vtkCommonCore import vtkDoubleArray
from vtkmodules.vtkFiltersCore import vtkImplicitPolyDataDistance
from vtkmodules.util.numpy_support import vtk_to_numpy

from audit_local import ROOT, read
from curved_cell_contact import set_coordinates, curved_skins
from dpf_readback import export
from extend_board import NODE
from film_identity import digest, verified, write_json
from global_contact import pair_summary
from installed_cell_gap import target_connectivity, hardware_face_grids
from native_rst import read_rst
from stage_snug_fit import AUDIT, MESH, STEP


def surface_owners(rst, mesh_file):
    with np.load(mesh_file) as mesh:
        face_by_nodes = {tuple(sorted(tri+NODE)): int(key)
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


def locked_geometry(rst, case, campaign):
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
    rows=[]
    for level in (2,3):
        cap, *targets=curved_skins(parts,level)
        distance=vtkImplicitPolyDataDistance()
        distance.SetInput(cap)
        for body,target in zip(target_ids,targets,strict=True):
            _,n=cap.collision(target,contact_mode=1,box_tolerance=0.,cell_tolerance=0.)
            output=vtkDoubleArray()
            distance.FunctionValue(target.GetPoints().GetData(),output)
            val=vtk_to_numpy(output)*1000
            assert len(val)==target.n_points and np.isfinite(val).all()
            rows.append(dict(subdivision=level,body=body,material=mapping[body],intersects=bool(n),
                             minimum_signed_target_vertex_gap_mm=float(val.min())))
    return dict(displacement_sha256=digest(suffix.with_suffix('.u')),node_ids_sha256=digest(suffix.with_suffix('.ids')),
                native_set=k,rows=rows)


def run(case,campaign):
    registered=read(AUDIT/'global_inputs.json')[case]
    verified(STEP,registered['step_sha256'])
    mesh=MESH/f"case_{registered['size_mm']}.npz";verified(mesh,registered['mesh_sha256'])
    parent=read(AUDIT/f'{case}_installed.json')
    assert parent['case']==case and parent['campaign']==campaign
    path=ROOT/'.runtime/archive'/campaign/case/'file.rst';verified(path,parent['rst_sha256'])
    rst=read_rst(path)
    owners=surface_owners(rst,mesh)
    history=contact_by_face(rst,owners,parent['contact_history'])
    results=dict(case=case,campaign=campaign,rst_sha256=parent['rst_sha256'],step_sha256=registered['step_sha256'],
                 case_mesh_sha256=registered['mesh_sha256'],number_of_contact_faces_by_STEP_face=dict(Counter(owners.values())),
                 loaded_STEP_face_geometry=loaded_face_geometry(history),contact_history=history,locked_geometry=locked_geometry(rst,case,campaign),
                 scope='Stored native contact corners grouped by exact case-mesh connectivity. Triangle intersection and signed target-vertex distances use the deformed quadratic case exterior and native hardware target faces at two subdivisions; vertex samples can miss face-to-face contact.')
    write_json(AUDIT/f'{case}_contacts.json',results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case');parser.add_argument('--campaign',default='nov08_01')
    args=parser.parse_args();run(args.case,args.campaign)

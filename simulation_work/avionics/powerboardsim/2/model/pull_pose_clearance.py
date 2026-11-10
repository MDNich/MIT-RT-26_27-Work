"""Place the edge-cell STEP and native target skin at measured poses before the first case reaction."""
import argparse
import math

import gmsh
import numpy as np
import pyvista as pv
from ansys.mapdl import reader
from scipy.spatial.transform import Rotation

from audit_local import ROOT, read, table
from case_drawdown_geometry import first_touch
from case_fit import old as board_step, case as case_step, PCB_CENTER, PCB_BOTTOM
from film_identity import digest, verified, write_json
from tab_seating import point_fields


def fitted_pose(path, mesh, pilot, history):
    nodes = table(path)
    attachment = np.array(mesh['attachment'])
    picked = np.searchsorted(nodes['node'], attachment)
    assert np.array_equal(nodes['node'][picked], attachment)
    initial = np.array([mesh['nodes'][str(n)] for n in attachment])
    archived = np.column_stack([nodes[a+'_mm'][picked] for a in 'xyz'])
    assert np.allclose(initial, archived, atol=1e-5, rtol=0)
    final = initial + np.column_stack([nodes['u'+a+'_mm'][picked] for a in 'xyz'])
    rotation, shift, residual = rigid_pose(initial, final, pilot)
    assert np.allclose(shift, [history['u'+a+'_mm'] for a in 'xyz'], atol=1e-6, rtol=0)
    return rotation, shift, residual


def rigid_pose(initial, final, pilot):
    x, y = initial.mean(0), final.mean(0)
    u, scales, vt = np.linalg.svd((initial-x).T @ (final-y))
    assert scales[-1] > 0 and np.linalg.det(u@vt) > 0
    rotation = Rotation.from_matrix((u@vt).T)
    shift = rotation.apply(pilot-x) + y - pilot
    residual = float(np.linalg.norm(rotation.apply(initial-x) + y - final, axis=1).max())
    assert residual < 1e-5
    return rotation, shift, residual


def native_surfaces(rst):
    grid = rst.quadgrid
    solid = grid.extract_cells(grid.cell_data['ansys_etype'] == 850)
    ids = solid.point_data['ansys_node_num']
    ix = np.searchsorted(rst.mesh.nnum, ids)
    assert np.array_equal(rst.mesh.nnum[ix], ids)
    solid.point_data['coords64'] = rst.mesh.nodes[ix]
    # Recover the selected CONTA174 faces independently from the full PLA exterior.
    contact = np.stack([e[10:18] for e in rst.mesh.elem if e[1] == 862 and e[2] == 861])
    assert np.array_equal(contact[:,2],contact[:,3]) and np.array_equal(contact[:,2],contact[:,6])
    contacts, local = np.unique(contact[:,[0,1,2,4,5,7]],return_inverse=True)
    mapping = np.searchsorted(rst.mesh.nnum,contacts)
    assert np.array_equal(rst.mesh.nnum[mapping],contacts)
    xyz = rst.mesh.nodes[mapping]
    patch = pv.UnstructuredGrid(np.column_stack((np.full(len(contact),6),local.reshape(-1,6))),
                                np.full(len(contact),pv.CellType.QUADRATIC_TRIANGLE),xyz)
    patch.point_data['coords64'] = xyz
    caps = []
    for level in (2, 3):
        cap = solid.extract_surface(nonlinear_subdivision=level, algorithm='dataset_surface').triangulate()
        cap.points = cap.point_data['coords64']
        assert not cap.n_open_edges
        targets = patch.extract_surface(nonlinear_subdivision=level, algorithm='dataset_surface').triangulate()
        targets.points = targets.point_data['coords64']
        assert targets.n_cells == len(contact)*4**level
        caps.append((cap,targets))
    # TARGE170 stores the third triangle node twice, and the pilot has no third node.
    facets = np.stack([e[10:14] for e in rst.mesh.elem if e[1] == 861 and e[2] == 861])
    faces = facets[facets[:,2] > 0]
    assert len(faces) == 2012 and len(facets) == len(faces)+1 and np.array_equal(faces[:,2], faces[:,3])
    ids, local = np.unique(faces[:,:3], return_inverse=True)
    ix = np.searchsorted(rst.mesh.nnum, ids)
    assert np.array_equal(rst.mesh.nnum[ix], ids)
    skin = pv.PolyData(rst.mesh.nodes[ix], np.column_stack((np.full(len(faces),3), local.reshape(-1,3))))
    assert not skin.n_open_edges
    return caps, skin, solid.point_data['ansys_node_num']


def run(case):
    root = ROOT/'validation'
    verdict, = [p for group in ('local','partial_local') if (p:=root/group/(case+'.json')).is_file()]
    proof = read(verdict)
    assert case.startswith('stand3_') and proof['case'] == case and proof['source'] == 'damage_cont_nominal'
    campaign = proof['campaign']
    folder = ROOT/'.runtime/archive'/campaign/case
    ledger = read(ROOT/'.runtime/receipts'/campaign/case/'archived.json')
    assert ledger['case'] == case and ledger['campaign'] == campaign
    hashes = {f['name']:f['sha256'] for f in ledger['files']}
    for name in ('tear.rst','history.csv','case_pairs.csv','set_inventory.csv'):
        verified(folder/name, hashes[name])
    assert hashes['tear.rst'] == proof['rst_sha256']
    mesh_path = ROOT/'.runtime/local_inputs/damage_cont_nominal/mesh.json'
    verified(mesh_path, read(root/'local_inputs.json')['damage_cont_nominal']['files']['mesh.json'])
    mesh = read(mesh_path)
    pilot = np.array(mesh['nodes'][str(mesh['pilot'])])
    inventory = table(folder/'set_inventory.csv')
    history = table(folder/'history.csv')
    pairs = table(folder/'case_pairs.csv')
    active = pairs[pairs['pair'] == 861]
    neighbour = pairs[pairs['pair'] == 862]
    assert np.array_equal(active['set'],inventory['set']) and np.array_equal(neighbour['set'],active['set'])
    first = np.flatnonzero(active['closed'] > 0)[0]
    assert np.all(neighbour['closed'][:first] == 0)
    for pair in (neighbour, active):
        assert all(np.all(pair['f'+a+'_N'][:first] == 0) for a in 'xyz')
    travel = inventory['ux_mm']
    assert np.allclose(travel[first-1:first+1],proof['pair_861']['contact_travel_bracket_mm'])
    # Only open equilibria: these models have no force on either added contact pair.
    # Sample the two original warm-up stations around geometric closure and the last open station.
    baseline = np.isclose(travel, .1375, atol=1e-8, rtol=0) | np.isclose(travel, .1875, atol=1e-8, rtol=0)
    selected = np.union1d(np.flatnonzero(baseline[:first]), [first-1])
    assert travel[selected[0]] > 0
    rst = reader.read_binary(folder/'tear.rst')
    caps, skin, solid_nodes = native_surfaces(rst)
    sets = inventory['set'][selected].astype(int)
    node_ids, displacements = point_fields(rst,sets,solid_nodes,field_directory='pull_pose')
    case_indices = np.searchsorted(node_ids,solid_nodes)
    assert np.array_equal(node_ids[case_indices],solid_nodes)
    case_motions = np.linalg.norm(displacements[:,case_indices],axis=2).max(axis=1)
    assert case_motions.max()<1e-7, 'The comparison with stationary case CAD needs an unloaded case'
    dpf_audit = ROOT/'.runtime/post'/campaign/case/'pull_pose/pilot_audit.json'
    original_skin = skin.points.copy()
    checked = []
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        occ = gmsh.model.occ
        hardware = occ.importShapes(str(board_step))
        cap, = occ.importShapes(str(case_step))
        occ.rotate([cap],0,0,0,1,0,0,-math.pi/2)
        occ.translate([cap],*PCB_CENTER,PCB_BOTTOM-13.)
        cell = (3,4)
        assert cell in hardware and np.linalg.norm(occ.getCenterOfMass(*cell)-pilot)<.001
        assert abs(skin.volume/occ.getMass(*cell)-1)<.002
        rest = float(occ.getDistance(*cap,*cell)[0])
        control, = [p for p in read(root/'rigid_cell_clearance.json') if p['step_body']==4 and p['direction']==1]
        assert np.isclose(rest, control['rest_distance_mm'], atol=1e-7, rtol=0)
        for i,motion in zip(selected,case_motions,strict=True):
            row, = history[np.isclose(history['time'],inventory['time'][i],atol=1e-7,rtol=0)]
            assert np.isclose(row['ux_mm'],travel[i],atol=1e-8,rtol=0)
            filename = f"nodes_{int(row['step'])}.csv"
            verified(folder/filename,hashes[filename])
            rotation, shift, residual = fitted_pose(folder/filename,mesh,pilot,row)
            moving, = occ.copy([cell])
            vec = rotation.as_rotvec()
            angle = np.linalg.norm(vec)
            if angle: occ.rotate([moving], *pilot, *(vec/angle), angle)
            occ.translate([moving], *shift)
            gap = float(occ.getDistance(*cap,*moving)[0])
            common, _ = occ.intersect([moving],[cap],removeObject=False,removeTool=False)
            volume = sum(occ.getMass(d,t) for d,t in common if d == 3)
            occ.remove(common,True)
            axial_excess = None
            if volume>0:
                # Keep the rotation and the two transverse translations at their measured
                # values. Only X changes during this auxiliary geometry calculation.
                def distance_at_x(x):
                    trial, = occ.copy([moving])
                    occ.translate([trial],float(x-shift[0]),0,0)
                    distance = float(occ.getDistance(*cap,*trial)[0])
                    occ.remove([trial],True)
                    return distance
                assert distance_at_x(0.)>1e-6
                lo,hi = first_touch(distance_at_x,stroke=shift[0],resolution=.00025)
                axial_excess = [float(shift[0]-hi),float(shift[0]-lo)]
            occ.remove([moving],True)
            assert (gap>1e-6 and volume==0) or (abs(gap)<=1e-6 and volume>0)
            skin.points = rotation.apply(original_skin-pilot) + pilot + shift
            levels = []
            for surface,patch in caps:
                _, on_patch = patch.collision(skin,contact_mode=1,box_tolerance=0.,cell_tolerance=0.)
                _, hit = surface.collision(skin,contact_mode=1,box_tolerance=0.,cell_tolerance=0.)
                signed = skin.compute_implicit_distance(surface)['implicit_distance']
                levels.append(dict(case_triangles=surface.n_cells,intersects=bool(hit),
                                   active_patch_triangles=patch.n_cells,active_patch_intersects=bool(on_patch),
                                   min_target_vertex_gap_mm=float(signed.min())))
            checked.append(dict(native_set=int(inventory['set'][i]),travel_mm=float(travel[i]),
                                force_N=float(inventory['fx_N'][i]),max_PLA_nodal_motion_mm=float(motion),rotation_vector_rad=vec.tolist(),
                                pilot_translation_mm=shift.tolist(),max_rigid_fit_error_mm=residual,
                                displacements_sha256=hashes[filename],CAD_gap_mm=gap,CAD_overlap_mm3=volume,
                                travel_past_first_CAD_touch_at_fixed_pose_mm=axial_excess,
                                meshed_geometry=levels))
    finally:
        gmsh.finalize()
    result=dict(case=case,fixture_sha256=digest(verdict),rst_sha256=proof['rst_sha256'],
                board_step_sha256=digest(board_step),case_step_sha256=digest(case_step),
                attachment_nodes=len(mesh['attachment']),PLA_nodes=len(solid_nodes),rest_CAD_gap_mm=rest,
                displacement_audit_sha256=digest(dpf_audit),
                native_contact_travel_bracket_mm=travel[first-1:first+1].tolist(),precontact_poses=checked,
                scope='Native cell poses against the registered case, with its negligible displacement verified using DPF. Solid intersection volume is a '
                      'geometric test. The native force law samples contact on mesh faces; this check does not '
                      'calculate an impact force or a corrected fixture reaction.')
    write_json(root/'pull_pose_clearance'/(case+'.json'),result)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('case')
    run(p.parse_args().case)

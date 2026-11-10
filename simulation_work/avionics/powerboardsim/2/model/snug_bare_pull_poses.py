"""Place the native bare pull's edge-cell poses in the registered, stationary snug pocket."""
import gmsh
import numpy as np
import pyvista as pv
from ansys.mapdl import reader
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersModeling import vtkCollisionDetectionFilter

from audit_local import ROOT, read, table
from case_fit import PCB_BOTTOM, PCB_CENTER, old
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from pull_pose_clearance import rigid_pose
from snug_surface_check import skin
from stage_snug_fit import AUDIT, MESH, SPACING, STEP, STEP_HASH
from tab_seating import point_fields


def bare_poses(source):
    case = 'bare_' + source
    verdict = ROOT/'validation/local'/f'{case}.json'
    proof = read(verdict)
    assert proof['full_requested_path'] and proof['case'] == case and proof['source'] == source
    campaign = proof['campaign']
    archive = ROOT/'.runtime/archive'/campaign/case
    receipt = ROOT/'.runtime/receipts'/campaign/case
    ledger = read(receipt/'archived.json')
    assert (receipt/'released.txt').is_file() and (ledger['campaign'], ledger['case']) == (campaign, case)
    hashes = {entry['name']: entry['sha256'] for entry in ledger['files']}
    for name in ('history.csv', 'nodal.csv', 'moving_supports.csv', 'model.inp', 'pull.rst'):
        verified(archive/name, hashes[name])
    assert hashes['pull.rst'] == proof['rst_sha256']
    mesh_path = ROOT/'.runtime/local_inputs'/source/'mesh.json'
    verified(mesh_path, read(ROOT/'validation/local_inputs.json')[source]['files']['mesh.json'])
    mesh = read(mesh_path)
    raw = reader.read_binary(archive/'pull.rst')
    nodes = np.asarray(mesh['attachment'])
    initial = raw.mesh.nodes[positions(raw.mesh.nnum, nodes)]
    assert np.max(abs(initial - [mesh['nodes'][str(n)] for n in nodes])) < 1e-7
    pilot = np.array(mesh['nodes'][str(mesh['pilot'])])
    history = table(archive/'history.csv')
    sets = np.arange(1,raw.nsets+1)
    assert np.array_equal(history['set'], sets) and np.allclose(raw.time_values,history['time'],atol=1e-8,rtol=0)
    ids, fields = point_fields(raw, sets, nodes, field_directory='edge_cell_poses')
    attachment = positions(ids,nodes)
    final = table(archive/'nodal.csv')
    exported = positions(final['node'],nodes)
    native_final = np.column_stack([final['u'+a+'_mm'][exported] for a in 'xyz'])
    endpoint_error = np.max(abs(native_final-fields[-1,attachment]))
    assert endpoint_error < 1e-7
    poses = []
    for row, displacements in zip(history,fields,strict=True):
        rotation, shift, error = rigid_pose(initial,initial+displacements[attachment],pilot)
        expected = np.array([row['u'+a+'_mm'] for a in 'xyz'])
        angles = np.array([row['rot'+a] for a in 'xyz'])
        assert np.max(abs(shift-expected)) < 1e-7
        # This local fixture rotates about Y. Verify that actual attachment motion recovers the pilot result.
        assert np.max(abs(rotation.as_rotvec()-angles)) < 1e-7
        poses.append((rotation,shift,error))
    control = ROOT/'.runtime/post'/campaign/case/'edge_cell_poses/pilot_audit.json'
    return pilot,history,poses,dict(case=case,verdict_sha256=digest(verdict),rst_sha256=hashes['pull.rst'],
        history_sha256=hashes['history.csv'],pose_readback_sha256=digest(control),input_sha256=hashes['model.inp'],
        mesh_sha256=digest(mesh_path),attachment_nodes=len(nodes),native_sets=len(sets),
        max_rigid_fit_error_mm=max(p[2] for p in poses),endpoint_DPF_vs_POST1_error_mm=float(endpoint_error))


def collision_probe(target, shell):
    transform = vtkTransform()
    detect = vtkCollisionDetectionFilter()
    detect.SetInputData(0,target)
    detect.SetInputData(1,shell)
    detect.SetTransform(0,transform)
    detect.SetTransform(1,vtkTransform())
    detect.SetCellTolerance(0.)
    detect.SetBoxTolerance(0.)
    detect.SetCollisionModeToFirstContact()
    def intersects(pilot, rotation, translation):
        matrix = np.eye(4)
        matrix[:3,:3] = rotation.as_matrix()
        matrix[:3,3] = pilot + translation - rotation.apply(pilot)
        transform.SetMatrix(matrix.ravel())
        detect.Update()
        return bool(detect.GetNumberOfContacts())
    return intersects


def run():
    reference = AUDIT/'local_rigid_side_clearance.json'
    rigid = read(reference)
    verified(STEP,STEP_HASH)
    verified(old,rigid['hardware_STEP_sha256'])
    verified(MESH/'case_2.npz',rigid['case_mesh_sha256'])
    verified(MESH/'fixture_targets_0005.npz',rigid['target_mesh_sha256'])
    with np.load(MESH/'fixture_targets_0005.npz') as targets:
        facets = targets['4']
        nodes,conn = np.unique(facets,return_inverse=True)
        moving = pv.PolyData(targets['points'][nodes],np.c_[np.full(len(facets),3),conn.reshape(-1,3)])
        assert moving.n_open_edges == 0
    with np.load(MESH/'case_2.npz') as mesh:
        probes = [collision_probe(moving,skin(mesh,level)) for level in (2,3)]

    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal',0)
        occ = gmsh.model.occ
        case, = occ.importShapes(str(STEP))
        occ.rotate([case],0,0,0,1,0,0,-np.pi/2)
        occ.translate([case],*PCB_CENTER,PCB_BOTTOM-10-SPACING)
        hardware = occ.importShapes(str(old))
        cell = hardware[3]
        assert abs(moving.volume / occ.getMass(*cell)-1) < .001
        assert abs(occ.getDistance(*cell,*case)[0]-rigid['initial_left_cell_gap_mm']) < 1e-7
        results = {}
        for label,source in [('positive_X','lateral_friction_locked'),('negative_X','lateral_friction_locked_minus')]:
            pilot,history,poses,result = bare_poses(source)
            assert np.linalg.norm(occ.getCenterOfMass(*cell)-pilot) < .001
            rows = []
            for row,(rotation,shift,_) in zip(history,poses,strict=True):
                copy, = occ.copy([cell])
                vector = rotation.as_rotvec()
                angle = np.linalg.norm(vector)
                if angle>1e-14:
                    occ.rotate([copy],*pilot,*(vector/angle),angle)
                occ.translate([copy],*shift)
                gap = float(occ.getDistance(*copy,*case)[0])
                mesh_hits = [probe(pilot,rotation,shift) for probe in probes]
                record = dict(native_set=int(row['set']),pilot_travel_mm=float(shift[0]),bare_reaction_N=float(row['fx_N']),
                              displacement_mm=shift.tolist(),rotation_rad=vector.tolist(),CAD_gap_mm=gap,
                              mesh_intersection_subdivisions_2_3=mesh_hits)
                if gap <= 1e-6:
                    common,_ = occ.intersect([case],[copy],removeObject=False,removeTool=False)
                    record['CAD_overlap_mm3'] = sum(occ.getMass(d,t) for d,t in common if d==3)
                    occ.remove(common,True)
                    assert record['CAD_overlap_mm3'] > 0
                occ.remove([copy],True)
                rows.append(record)
                if gap <= 1e-6:
                    break
            assert len(rows)>1 and rows[-1]['CAD_gap_mm']<=1e-6 and rows[-2]['CAD_gap_mm']>1e-6
            assert all(r['mesh_intersection_subdivisions_2_3']==[False,False] for r in rows[:-1])
            assert rows[-1]['mesh_intersection_subdivisions_2_3']==[True,True]
            results[label] = dict(**result,states_through_first_overlap=rows,
                signed_travel_bracket_mm=[r['pilot_travel_mm'] for r in rows[-2:]],
                bare_force_at_bracketing_states_N=[r['bare_reaction_N'] for r in rows[-2:]])
    finally:
        gmsh.finalize()
    write_json(AUDIT/'bare_pull_poses_in_case.json',dict(rigid_control_sha256=digest(reference),directions=results,
        scope='The bare bilinear nickel fixture supplies the poses and reactions. CAD and the two reconstructed '
              'case meshes are stationary. The brackets identify adjacent sampled bare states changing from positive '
              'clearance to solid overlap. Cased contact force requires the separate nonlinear fixture.'))


if __name__=='__main__':
    run()

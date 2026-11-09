"""Compare undeformed FE surface contact during assembly against the registered STEP sweep."""
import sys

import numpy as np
import pyvista as pv
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersModeling import vtkCollisionDetectionFilter

from audit_local import ROOT, read
from case_fit import PCB_BOTTOM, PCB_CENTER
from clearance_response import surface
from extend_board import FACE_MATERIALS, NODE
from film_identity import digest, verified, write_json
from native_rst import read_rst


def case_skin(size):
    """Subdivide the quadratic boundary triangles at their actual midside nodes."""
    path = ROOT / f'.runtime/mesh/case_{size}.npz'
    with np.load(path) as mesh:
        local = mesh['points']
        nodes = np.column_stack((PCB_CENTER[0] + local[:, 0], PCB_CENTER[1] + local[:, 2],
                                 PCB_BOTTOM - 13. - local[:, 1])) * .001
        triangles = np.concatenate([mesh[k] for k in mesh.files if k.isdigit()])
    pattern = np.array([[0, 3, 5], [3, 1, 4], [5, 4, 2], [3, 4, 5]])
    faces = triangles[:, pattern].reshape(-1, 3)
    selected, remapped = np.unique(faces, return_inverse=True)
    skin = pv.PolyData.from_regular_faces(nodes[selected], remapped.reshape(-1, 3))
    assert skin.is_manifold
    return skin, selected + NODE, digest(path)


def bracket(case, target):
    moving, fixed = vtkTransform(), vtkTransform()
    collision = vtkCollisionDetectionFilter()
    collision.SetInputData(0, case)
    collision.SetInputData(1, target)
    collision.SetTransform(0, moving)
    collision.SetTransform(1, fixed)
    collision.SetCollisionModeToFirstContact()
    collision.SetBoxTolerance(0.)
    collision.SetCellTolerance(0.)

    def intersects(travel_mm):
        moving.Identity()
        moving.Translate(0., 0., travel_mm * .001)
        collision.Update()
        return collision.GetNumberOfContacts() > 0

    assert not intersects(0.)
    for sample in range(1, 61):
        high = sample / 20
        if intersects(high):
            low = (sample - 1) / 20
            while high - low > .00025:
                mid = (low + high) / 2
                if intersects(mid):
                    high = mid
                else:
                    low = mid
            assert not intersects(low) and intersects(high)
            return [low, high]
    return None


def run(campaign):
    case = 'stand3_nylon_static'
    proof = read(ROOT / 'validation/global' / f'{case}.json')
    assert proof['campaign'] == campaign
    path = ROOT / '.runtime/archive' / campaign / case / 'file.rst'
    verified(path, proof['rst_sha256'])
    rst = read_rst(path)
    solids = {mat: surface(rst, [mat])[0] for mat in FACE_MATERIALS}
    native_skin, native_faces, native_ids, _ = surface(rst, [850])

    paths = ROOT / 'validation'
    cad_path = paths / 'rigid_case_drawdown.json'
    cad = {r['native_material']: r for r in read(cad_path)['records']}
    nominal, ids, nominal_sha = case_skin(3)
    order = np.argsort(native_ids)
    assert np.array_equal(native_ids[order], ids)
    assert np.max(np.abs(nominal.points - native_skin.points[order])) < 1e-11

    def connectivity(faces, ids):
        triangles = np.sort(ids[faces], axis=1)
        return triangles[np.lexsort(triangles.T)]
    assert np.array_equal(connectivity(native_faces, native_ids), connectivity(nominal.regular_faces, ids))

    refined, _, refined_sha = case_skin(2)
    results = {}
    for mat, target in solids.items():
        record = cad[mat]
        steps = record['first_touch_travel_bracket_mm']
        nominal_steps = bracket(native_skin, target)
        refined_steps = bracket(refined, target)
        print(mat, steps, nominal_steps, refined_steps, flush=True)
        results[mat] = dict(STEP_body=record['STEP_body'], STEP_mm=steps,
                            native_skin_mm=nominal_steps, refined_case_skin_mm=refined_steps)

    # The middle cell first grazes a curved wall. Compare geometric sampling of the
    # same native quadratic elements to isolate this error from solver convergence.
    grid = rst.quadgrid
    def body(material):
        mask = np.isin(grid.cell_data['ansys_elem_type_num'], [185, 186, 187])
        return grid.extract_cells(mask & (grid.cell_data['ansys_material_type'] == material))

    def tessellate(domain, subdivisions):
        return domain.extract_surface(algorithm='dataset_surface', nonlinear_subdivision=subdivisions).triangulate()

    middle = next(mat for mat in solids if cad[mat]['STEP_body'] == 19)
    native_case, native_cell = body(850), body(middle)
    curvature = {'1': results[middle]['native_skin_mm']}
    for subdivisions in (2, 3, 4):
        curvature[str(subdivisions)] = bracket(tessellate(native_case, subdivisions), tessellate(native_cell, subdivisions))
    assert all(curvature.values())
    print('Middle cell, quadratic-surface subdivisions', curvature, flush=True)

    write_json(paths / 'rigid_mesh_drawdown.json', dict(
        campaign=campaign, undeformed_geometry_RST_sha256=proof['rst_sha256'],
        case_mesh_sha256={'3mm': nominal_sha, '2mm': refined_sha}, STEP_audit_sha256=digest(cad_path),
        search_step_mm=.05, bracket_tolerance_mm=.00025, results=results,
        middle_cell_native_quadratic_subdivision=curvature,
        scope='Rigid vertical translation with fixed original hardware. The native and refined PLA surface '
              'meshes use quadratic midside nodes. Each bracket refines the first intersection detected on '
              'a 0.05 mm grid. The independent STEP sweep bounds first contact continuously.'))


if __name__ == '__main__':
    run(sys.argv[1])

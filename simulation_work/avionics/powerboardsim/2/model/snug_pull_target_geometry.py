"""Compare the native cell target and two finer skins with the trimmed STEP solid at fixed native pull poses."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pyvista as pv
from ansys.mapdl import reader
from audit_local import ROOT, read
from case_fit import old as BOARD_STEP
from film_identity import digest, verified, write_json
from local_case_geometry import target_skin
from local_equilibrium import positions
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.gp import gp_Pnt
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_IN, TopAbs_ON, TopAbs_OUT, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from pull_pose_clearance import rigid_pose
from snug_local_checkpoint import CASE
from snug_pocket_faces import SHAPE, SIX
from snug_pull_pressure import DU, DV, contact_index, dpf_fields, loaded_faces
from stage_snug_fit import AUDIT, MESH
from vtkmodules.util.numpy_support import numpy_to_vtk, vtk_to_numpy
from vtkmodules.vtkCommonCore import vtkDoubleArray
from vtkmodules.vtkFiltersCore import vtkImplicitPolyDataDistance

CACHE = ROOT / ".runtime/qa/snug125/pull-faceting"
BASE = CASE + "_ls3_ss18"
TOL_MM = 1e-8


def cell_geometry():
    cad = STEPControl_Reader()
    assert cad.ReadFile(str(BOARD_STEP)) == IFSelect_RetDone and cad.TransferRoots()
    solids = TopExp_Explorer(cad.OneShape(), TopAbs_SOLID)
    cells = []
    index = 0
    while solids.More():
        index += 1
        solid = solids.Current()
        solids.Next()
        prop = GProp_GProps()
        BRepGProp.VolumeProperties_s(solid, prop)
        if 25000 < prop.Mass() < 25400:
            cells.append((prop.CentreOfMass().X(), index, solid))
    cells.sort(key=lambda t: t[0])
    assert [c[1] for c in cells] == [4, 19, 15]
    solid = cells[0][2]
    shell = TopExp_Explorer(solid, TopAbs_SHELL)
    boundary = shell.Current()
    shell.Next()
    assert not shell.More()
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(solid, box, False, True)
    return solid, boundary, np.array([box.CornerMin().Coord(), box.CornerMax().Coord()])


def native_skin(raw, skin):
    faces = skin["4"]
    target = [e[10:13] - 1600000 for e in raw.mesh.elem if e[1] == 861 and e[2] == 861 and e[12] > 0]

    def oriented(f):
        return {tuple(np.roll(t, -np.argmin(t))) for t in f}

    assert len(faces) == len(target) and oriented(faces) == oriented(target)
    ids, ix = np.unique(faces, return_inverse=True)
    xyz = raw.mesh.nodes[positions(raw.mesh.nnum, 1600000 + ids)]
    np.testing.assert_allclose(xyz, skin["points"][ids], rtol=0, atol=1e-6)
    return xyz, ix.reshape(-1, 3)


def generated_skin(name, tolerances, *, expected=None):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.npz"
    if expected and path.is_file():
        verified(path, expected)
        return path
    with TemporaryDirectory(prefix=name + "-", dir=CACHE) as tmp:
        fresh = Path(tmp) / path.name
        target_skin(out=fresh, cell_resolution=tolerances)
        if expected:
            assert digest(fresh) == expected
        try:
            path.hardlink_to(fresh)
        except FileExistsError:
            with np.load(fresh) as new, np.load(path) as old:
                assert set(old.files) == set(new.files)
                for key in new.files:
                    np.testing.assert_array_equal(old[key], new[key])
    if expected:
        verified(path, expected)
    return path


def skins(raw, skin_sha):
    sources = {}
    search = {}
    CACHE.mkdir(parents=True, exist_ok=True)
    for name, tolerances in [
        ("native", (0.0005, 0.016)),
        ("fine", (0.000125, 0.008)),
        ("finer", (0.00003125, 0.004)),
    ]:
        if name == "native":
            path = MESH / "fixture_targets_0005.npz"
            verified(path, skin_sha)
        else:
            path = generated_skin(name, tolerances)
        with np.load(path) as data:
            if name == "native":
                xyz, conn = native_skin(raw, data)
            else:
                ids, ix = np.unique(data["4"], return_inverse=True)
                conn = ix.reshape(-1, 3)
                # Apply the same APDL coordinate precision used in the staged native fixture.
                xyz = np.array([[float(f"{v:.9g}") for v in pt] for pt in data["points"][ids]])
        surface = pv.PolyData(xyz, np.c_[np.full(len(conn), 3), conn])
        assert surface.n_open_edges == 0 and surface.is_manifold
        engine = vtkImplicitPolyDataDistance()
        engine.SetInput(surface)
        search[name] = engine
        sources[name] = {
            "triangles": len(conn),
            "points": len(xyz),
            "linear_deflection_mm": tolerances[0],
            "angular_deflection_rad": tolerances[1],
            "skin_sha256": digest(path),
        }
    return sources, search


def cad_distances(points, mesh_gap, geometry):
    solid, shell, box = geometry
    classifier = BRepClass3d_SolidClassifier(solid)
    inside = np.zeros(len(points), bool)
    on = np.zeros(len(points), bool)
    for j in np.flatnonzero(((points >= box[0] - TOL_MM) & (points <= box[1] + TOL_MM)).all(axis=1)):
        classifier.Perform(gp_Pnt(*points[j]), TOL_MM)
        state = classifier.State()
        assert state in (TopAbs_IN, TopAbs_ON, TopAbs_OUT)
        inside[j], on[j] = state == TopAbs_IN, state == TopAbs_ON

    # Include every interior/boundary point, the nearest exterior station when all are clear,
    # and every point within one micrometre of the native faceted cell.
    chosen = inside | on | (mesh_gap <= max(0.001, mesh_gap.min() + 0.0002))
    distance = BRepExtrema_DistShapeShape()
    distance.LoadS2(shell)
    values = []
    for j in np.flatnonzero(chosen):
        distance.LoadS1(BRepBuilderAPI_MakeVertex(gp_Pnt(*points[j])).Vertex())
        assert distance.Perform() and distance.IsDone()
        value = distance.Value()
        assert value >= 0 and (not on[j] or value <= 1e-6)
        values.append(-value if inside[j] else value)
    return chosen, inside, on, np.array(values)


def run():
    folder = ROOT / ".runtime/qa/snug125/forward-readback/ls3_ss18"
    checkpoint_path, pressure_path = (AUDIT / f"{BASE}_{s}.json" for s in ("checkpoint", "cell_pressure"))
    check, pressure = map(read, (checkpoint_path, pressure_path))
    assert (
        pressure["checkpoint_sha256"] == digest(checkpoint_path) and pressure["rst_sha256"] == check["rst_sha256"]
    )
    spec = read(AUDIT / "local_rigid_side_clearance_m15.json")
    verified(BOARD_STEP, spec["hardware_STEP_sha256"])
    verified(folder / "pull.rst", check["rst_sha256"])
    verified(folder / "dpf_points/displacements.bin", check["pose_check"]["DPF_translations_sha256"])
    raw = reader.read_binary(folder / "pull.rst")
    source, search = skins(raw, spec["target_mesh_sha256"])
    geometry = cell_geometry()
    nodes, field = dpf_fields(folder / "dpf_points", check["rst_sha256"])
    mesh = read(ROOT / ".runtime/local_inputs/lateral_friction_locked/mesh.json")
    attached = np.array(mesh["attachment"])
    rest = raw.mesh.nodes[positions(raw.mesh.nnum, attached)]
    pilot = raw.mesh.nodes[positions(raw.mesh.nnum, [mesh["pilot"]])][0]
    index = contact_index(raw)
    elements = [e for e in index[0] if e[2] == 861]
    ids = np.array([e[8] for e in elements])
    faces = np.array([e[10:18][SIX] for e in elements])
    xyz = raw.mesh.nodes[positions(raw.mesh.nnum, faces)]
    where = positions(nodes, faces)
    records = []
    for ref in pressure["states"]:
        k = ref["native_set"]
        u = field[k]
        rotation, shift, fit = rigid_pose(rest, rest + u[positions(nodes, attached)], pilot)
        assert fit < 1e-8 and abs(shift[0] - ref["travel_mm"]) < 1e-8
        deformed = xyz + u[where]
        q = (SHAPE.T @ deformed).reshape(-1, 3)
        areas = (np.linalg.norm(np.cross(DU @ deformed, DV @ deformed), axis=2) / 6).ravel()
        points = pilot + rotation.inv().apply(q - pilot - shift)
        gaps = {}
        for name, engine in search.items():
            output = vtkDoubleArray()
            engine.EvaluateFunction(numpy_to_vtk(np.ascontiguousarray(points)), output)
            gaps[name] = vtk_to_numpy(output).copy()
        status = np.zeros((len(faces), 3), bool)
        signature = sha256()
        for e, _, stress, _ in loaded_faces(raw, index, k, signature):
            if e[2] == 861:
                status[positions(ids, [e[8]])[0]] = stress[:3] > 0
        assert signature.hexdigest() == ref["native_pressure_records_sha256"]
        status = status.ravel()
        chosen, _inside, on, cad = cad_distances(points, gaps["native"], geometry)
        # CAD border classifications and distances under the geometric tolerance are undecided.
        definitely_in = np.zeros(len(points), bool)
        definitely_in[chosen] = (cad < -TOL_MM) & ~on[chosen]
        uncertain = np.zeros(len(points), bool)
        uncertain[chosen] = on[chosen] | (abs(cad) <= TOL_MM)
        native = gaps["native"]
        mismatch = (native < 0) != status
        data = {}
        for name, g in gaps.items():
            delta = (g[chosen] - cad) * 1000
            data[name] = {
                "inside_points": int((g < -TOL_MM).sum()),
                "CAD_inside_skin_clear": int((definitely_in & (g > TOL_MM)).sum()),
                "skin_inside_CAD_clear": int(((g < -TOL_MM) & ~definitely_in & ~uncertain).sum()),
                "near_boundary_points": int((abs(g) <= TOL_MM).sum()),
                "area_at_inside_points_mm2": float(areas[g < -TOL_MM].sum()),
                "max_error_in_checked_gaps_um": float(np.max(abs(delta))),
                "min_signed_gap_um": 1000 * float(g.min()),
            }
        assert status.sum() == ref["cells"].get("4", {}).get("loaded_points", 0)
        assert np.all(abs(native[mismatch]) < 2e-6), (k, native[mismatch])
        np.testing.assert_allclose(
            areas[status].sum(), ref["cells"].get("4", {}).get("contact_area_mm2", 0.0), rtol=1e-7, atol=1e-8
        )
        records.append(
            {
                "native_set": k,
                "travel_mm": ref["travel_mm"],
                "actuator_N": ref["actuator_N"],
                "native_loaded_points": int(status.sum()),
                "mesh_sign_vs_native_disagreements": int(mismatch.sum()),
                "largest_mismatch_distance_um": float(1000 * np.max(abs(native[mismatch]), initial=0)),
                "CAD_intrusions_deeper_than_1nm": int((cad < -1e-6).sum()),
                "exact_CAD_inside_points": int(definitely_in.sum()),
                "CAD_inside_point_area_mm2": float(areas[definitely_in].sum()),
                "native_loaded_area_mm2": float(areas[status].sum()),
                "CAD_uncertain_area_mm2": float(areas[uncertain].sum()),
                "CAD_boundary_uncertain_points": int(uncertain.sum()),
                "inside_CAD_without_native_load": int((definitely_in & ~status).sum()),
                "native_load_outside_CAD": int((status & ~definitely_in & ~uncertain).sum()),
                "min_CAD_gap_among_checked_points_um": float(1000 * cad.min()),
                "exact_boundary_distance_queries": int(chosen.sum()),
                "fitted_pose_error_mm": fit,
                "skins": data,
            }
        )
        print(
            k,
            int(status.sum()),
            [s["inside_points"] for s in data.values()],
            definitely_in.sum(),
            uncertain.sum(),
            flush=True,
        )
    write_json(
        AUDIT / "moving_cell_target_resolution.json",
        {
            "case": CASE,
            "checkpoint_sha256": digest(checkpoint_path),
            "pressure_sha256": digest(pressure_path),
            "hardware_STEP_sha256": spec["hardware_STEP_sha256"],
            "source_rst_sha256": check["rst_sha256"],
            "moving_case_triangles": len(faces),
            "points_per_station": 3 * len(faces),
            "CAD_classification_tolerance_mm": TOL_MM,
            "cell_skins": source,
            "states": records,
            "scope": "Independent signed distances on unchanged native displacements of the 1.5 mm PLA mesh. "
            "The native target and two finer triangulations use the same STEP cell. Its trimmed CAD solid "
            "classifies all Gauss points after a bounding-box exclusion. Negative gap means intrusion "
            "at the prescribed pose. Only the original mesh has native pressure and equilibrium.",
        },
    )


if __name__ == "__main__":
    run()

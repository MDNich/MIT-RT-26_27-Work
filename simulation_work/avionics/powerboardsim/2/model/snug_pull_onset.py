"""Locate the first edge-cell contact using the native bare pull paths in both directions."""

import itertools

import gmsh
import numpy as np
import pyvista as pv
from ansys.mapdl import reader
from audit_local import ROOT, read
from case_fit import PCB_BOTTOM, PCB_CENTER, old
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from pull_pose_clearance import rigid_pose
from scipy.interpolate import PchipInterpolator
from scipy.spatial.transform import Rotation
from snug_bare_pull_poses import bare_poses
from snug_local_checkpoint import CAMPAIGN, CASE
from snug_pocket_faces import SHAPE, SIX
from stage_snug_fit import AUDIT, INPUTS, MESH, SPACING, STEP, STEP_HASH
from vtkmodules.util.numpy_support import numpy_to_vtk, vtk_to_numpy
from vtkmodules.vtkCommonCore import vtkDoubleArray
from vtkmodules.vtkFiltersCore import vtkImplicitPolyDataDistance


def independent_distance(point, triangles):
    """Check the closest triangle and inside sign against three independent parity rays."""
    a, b, c = triangles.transpose(1, 0, 2)
    e1, e2 = b - a, c - a
    normal = np.cross(e1, e2)
    l2 = np.einsum("ij,ij->i", normal, normal)
    r = point - a
    u = np.einsum("ij,ij->i", np.cross(r, e2), normal) / l2
    v = np.einsum("ij,ij->i", np.cross(e1, r), normal) / l2
    inside = (u >= 0) & (v >= 0) & (u + v <= 1)
    distance = np.min(
        np.abs(np.einsum("ij,ij->i", r, normal)[inside]) / np.sqrt(l2[inside]), initial=np.inf
    )
    for x, y in ((a, b), (b, c), (c, a)):
        delta = y - x
        t = np.clip(np.einsum("ij,ij->i", point - x, delta) / np.sum(delta**2, axis=1), 0, 1)
        distance = min(distance, np.linalg.norm(point - x - delta * t[:, None], axis=1).min())
    votes = []
    for ray in ((0.321, 0.451, 0.977), (-0.721, 0.116, 0.509), (0.263, -0.814, 0.098)):
        h = np.cross(ray, e2)
        det = np.einsum("ij,ij->i", e1, h)
        ix = np.flatnonzero(abs(det) > 1e-13)
        q = np.cross(r[ix], e1[ix])
        ru = np.einsum("ij,ij->i", r[ix], h[ix]) / det[ix]
        rv = (q @ ray) / det[ix]
        dt = np.einsum("ij,ij->i", e2[ix], q) / det[ix]
        hits = (ru >= 0) & (rv >= 0) & (ru + rv <= 1) & (dt > 0)
        votes.append(int(np.count_nonzero(hits) % 2))
    assert len(set(votes)) == 1, votes
    return float(distance * (-1 if votes[0] else 1))


class BarePath:
    def __init__(self, direction, method, pilot, history, poses):
        self.pilot = pilot
        keep = history["time"] >= 2.0
        self.sign = 1 if direction == "positive_X" else -1
        self.travel = self.sign * history["ux_mm"][keep]
        self.travel[0] = 0.0
        assert np.all(np.diff(self.travel) > 0) and abs(self.travel[-1] - 0.5) < 1e-8
        self.values = np.array(
            [
                np.r_[shift, rot.as_rotvec(), row["fx_N"]]
                for (rot, shift, _), row, take in zip(poses, history, keep, strict=True)
                if take
            ]
        )
        self.method = method
        self.spline = PchipInterpolator(self.travel, self.values, extrapolate=False)

    def at(self, x):
        if self.method == "pchip":
            return self.spline(x)
        return np.array([np.interp(x, self.travel, column) for column in self.values.T])

    def inverse(self, points, x):
        val = self.at(x)
        return self.pilot + Rotation.from_rotvec(val[3:6]).inv().apply(points - self.pilot - val[:3])

    def motion_bound(self, a, b, radius):
        # On one monotone Hermite interval the total variation of each component equals its
        # endpoint difference. The SO(3) exponential maps rotation-vector path length to
        # angular path length with gain at most one. Radius encloses the moving body or points.
        change = abs(self.at(a) - self.at(b))
        return change[:3].sum() + radius * change[3:6].sum()


def first_contact(path, gap, radius, last, *, tolerance=1e-10):
    knots = [float(v) for v in path.travel if v < last] + [last]
    gaps = {}

    def value(x):
        if x not in gaps:
            gaps[x] = gap(x)
        return gaps[x]

    first = next(i for i, x in enumerate(knots) if value(x) <= tolerance)
    assert first > 0
    a, b = knots[first - 1 : first + 1]
    while b - a > 1e-7:
        m = (a + b) / 2
        if value(m) > tolerance:
            a = m
        else:
            b = m
    # Verify the preceding continuous trajectory. The negative endpoint gives the upper
    # bound even if another point crosses between two originally saved bare equilibria.
    lo = max(knots[first - 1], a - 2e-6)
    prior = knots[:first] + [lo]
    stack = list(itertools.pairwise(prior))
    leaves = 0
    while stack:
        x, y = stack.pop()
        separation = max(value(x), value(y)) - path.motion_bound(x, y, radius)
        if separation > tolerance:
            leaves += 1
            continue
        if y - x < 1e-9:
            raise ValueError(f"Earlier contact could not be excluded at {x:g} mm")
        mid = (x + y) / 2
        stack.extend(((x, mid), (mid, y)))
    return {
        "travel_magnitude_mm": [lo, b],
        "separation_mm": [value(lo), value(b)],
        "bare_reaction_N": [float(path.at(x)[-1]) for x in (lo, b)],
        "verified_clear_intervals": leaves,
        "geometry_evaluations": len(gaps),
    }


def primary_inputs():
    catalog = read(AUDIT / "local_inputs_m15.json")
    hashes = {}
    reference = (INPUTS / CASE / "model.inp").read_text().splitlines()
    for material in ("nylon", "aluminium"):
        for reverse in (False, True):
            suffix = "_minus" if reverse else ""
            name = f"snug125_{material}_lateral_friction_locked{suffix}_pin1_m15"
            spec = catalog[name]
            path = INPUTS / name / "model.inp"
            hashes[name] = verified(path, spec["input_sha256"])
            allowed = {}
            if reverse:
                allowed = {f"R,{i},,,.1,.01,,.2": f"R,{i},,,0.1,.01,,.2" for i in range(1, 5)}
                allowed["D,2481,UX,0.5"] = "D,2481,UX,-0.5"
            if material == "aluminium":
                allowed.update(
                    {
                        "MP,EX,851,3000.0": "MP,EX,851,69000.0",
                        "MP,PRXY,851,0.39": "MP,PRXY,851,0.33",
                        "MP,DENS,851,1.14e-09": "MP,DENS,851,2.6999999999999998e-09",
                    }
                )
            differences = [
                (a, b) for a, b in zip(reference, path.read_text().splitlines(), strict=True) if a != b
            ]
            assert len(differences) == len(allowed) and dict(differences) == allowed
            assert spec["bare_reference"] == "bare_lateral_friction_locked" + suffix
    return hashes


def native_fixture():
    snap = ROOT / ".runtime/qa/snug125/forward-readback/ls3_ss12"
    proof_path = AUDIT / f"{CASE}_ls3_ss12_checkpoint.json"
    proof = read(proof_path)
    verified(snap / "pull.rst", proof["rst_sha256"])
    raw = reader.read_binary(str(snap / "pull.rst"))
    con = [e for e in raw.mesh.elem if e[1] == 862 and e[2] == 861]
    tar = [e for e in raw.mesh.elem if e[1] == 861 and e[2] == 861 and e[12] > 0]
    ids = np.asarray([e[8] for e in con])
    faces = np.array([e[10:18][SIX] for e in con])
    tri = np.array([e[10:13] for e in tar])
    target_xyz = raw.mesh.nodes[positions(raw.mesh.nnum, tri)]
    chk = read(AUDIT / "local_rigid_side_clearance_m15.json")
    assert chk["case_STEP_sha256"] == STEP_HASH
    verified(MESH / "fixture_targets_0005.npz", chk["target_mesh_sha256"])
    with np.load(MESH / "fixture_targets_0005.npz") as mesh:
        native_ids = tri - 1600000

        def oriented_order(faces):
            i = faces.argmin(axis=1)
            cyclic = np.take_along_axis(faces, (i[:, None] + np.arange(3)) % 3, axis=1)
            return cyclic[np.lexsort(cyclic.T)]

        np.testing.assert_array_equal(oriented_order(native_ids), oriented_order(mesh["4"]))
        np.testing.assert_allclose(mesh["points"][native_ids], target_xyz, atol=1e-6, rtol=0)
    target_nodes, ix = np.unique(tri, return_inverse=True)
    poly = pv.PolyData(
        raw.mesh.nodes[positions(raw.mesh.nnum, target_nodes)],
        np.c_[np.full(len(tri), 3), ix.reshape(-1, 3)],
    )
    assert poly.n_open_edges == 0
    engine = vtkImplicitPolyDataDistance()
    engine.SetInput(poly)

    def distances(x):
        out = vtkDoubleArray()
        engine.EvaluateFunction(numpy_to_vtk(np.ascontiguousarray(x)), out)
        return vtk_to_numpy(out).copy()

    with np.load(MESH / "case_1.5.npz") as mesh:
        verified(MESH / "case_1.5.npz", chk["case_mesh_sha256"])
        tags = {tuple(sorted(f + 2100001)): t for t in (10, 11, 12, 13) for f in mesh[str(t)]}
    assert len(tags) == len(faces) and set(tags) == set(map(tuple, np.sort(faces, axis=1)))
    native = raw.mesh.nodes[positions(raw.mesh.nnum, faces)]
    # Check the free pocket remained stationary through the last unloaded native pull station.
    folder = snap / "dpf_points"
    field = read(folder / "request.json")
    verified(folder / "displacements.bin", proof["pose_check"]["DPF_translations_sha256"])
    disp = np.memmap(
        folder / "displacements.bin", "<f8", "r", shape=(raw.nsets, len(field["nodes"]), 3)
    )
    unloaded = [
        r
        for r in proof["states"]
        if r["native_set"] < proof["first_loaded_moving_cell_bracket"][1]["native_set"]
    ]
    assert len(unloaded) == unloaded[-1]["native_set"]
    pre_u = float(
        abs(disp[: len(unloaded), positions(np.array(field["nodes"]), np.unique(faces))]).max()
    )
    assert pre_u < 1e-8

    def quadrature(x):
        return np.einsum("ng,fnk->fgk", SHAPE, x).reshape(-1, 3)

    grids = {
        "native_1.5_mm": (
            quadrature(native),
            np.repeat([tags[tuple(sorted(f))] for f in faces], 3),
            np.repeat(ids, 3),
        )
    }
    coarse = read(AUDIT / "local_rigid_side_clearance_m3.json")
    assert coarse["case_STEP_sha256"] == STEP_HASH
    verified(MESH / "case_3.npz", coarse["case_mesh_sha256"])
    with np.load(MESH / "case_3.npz") as mesh:
        local = mesh["points"]
        xyz = np.column_stack(
            (PCB_CENTER[0] + local[:, 0], PCB_CENTER[1] + local[:, 2], PCB_BOTTOM - 10 - SPACING - local[:, 1])
        )
        triangles = np.vstack([mesh[str(t)] for t in (10, 11, 12, 13)])
        labels = np.repeat([t for t in (10, 11, 12, 13) for _ in mesh[str(t)]], 3)
        grids["3_mm"] = (quadrature(xyz[triangles]), labels, None)
    return raw, grids, distances, target_xyz, proof, pre_u


def cad_onset(path, stop, initial):
    """Independent exact STEP solids on the same interpolated rigid path."""
    occ = gmsh.model.occ
    gmsh.model.add("cell_fit")
    try:
        (case,) = occ.importShapes(str(STEP))
        occ.rotate([case], 0, 0, 0, 1, 0, 0, -np.pi / 2)
        occ.translate([case], *PCB_CENTER, PCB_BOTTOM - 10 - SPACING)
        cell = occ.importShapes(str(old))[3]
        assert abs(occ.getDistance(*cell, *case)[0] - initial) < 1e-7
        box = np.array(occ.getBoundingBox(*cell)).reshape(2, 3)
        radius = np.linalg.norm(np.max(abs(box - path.pilot), axis=0)) + 1.0

        def placed(x):
            (moved,) = occ.copy([cell])
            state = path.at(x)
            vector = state[3:6]
            angle = np.linalg.norm(vector)
            if angle > 1e-14:
                occ.rotate([moved], *path.pilot, *(vector / angle), angle)
            occ.translate([moved], *state[:3])
            return moved

        def gap(x):
            moved = placed(x)
            value = occ.getDistance(*moved, *case)[0]
            occ.remove([moved], recursive=True)
            return float(value)

        crossing = first_contact(path, gap, radius, stop, tolerance=1e-6)
        # A near-tangent intersection can have zero Boolean volume at the CAD kernel's
        # tolerance. Keep the first positive volume and its actual position as a separate bound.
        for extra in (1e-5, 5e-5, 0.0001, 0.0005, 0.001, stop):
            sample = min(stop, crossing["travel_magnitude_mm"][1] + extra)
            delta = placed(sample)
            pieces, _ = occ.intersect([case], [delta], removeObject=False, removeTool=False)
            volume = sum(occ.getMass(*body) for body in pieces if body[0] == 3)
            occ.remove(pieces, True)
            occ.remove([delta], True)
            if volume > 0:
                break
        assert volume > 0, (sample, volume)
        crossing.update(
            gap_tolerance_mm=1e-6,
            overlap_sample_mm=sample,
            positive_overlap_mm3=volume,
            clear_to_volume_overlap_mm=[crossing["travel_magnitude_mm"][0], sample],
        )
        return crossing
    finally:
        gmsh.model.remove()


def native_first_loaded_pose(raw, proof, distances, tri, pilot, onset):
    """Locate the predicted first point in the subsequently deformed native contact patch."""
    folder = ROOT / ".runtime/qa/snug125/forward-readback/ls3_ss12/dpf_points"
    req = read(folder / "request.json")
    ids = np.array(req["nodes"])
    number = proof["first_loaded_moving_cell_bracket"][1]["native_set"]
    field = np.memmap(folder / "displacements.bin", "<f8", "r", shape=(raw.nsets, len(ids), 3))[
        number - 1
    ]
    mesh = read(ROOT / ".runtime/local_inputs/lateral_friction_locked/mesh.json")
    attach = np.array(mesh["attachment"])
    rest = raw.mesh.nodes[positions(raw.mesh.nnum, attach)]
    rotation, shift, error = rigid_pose(rest, rest + field[positions(ids, attach)], pilot)
    assert error < 1e-6
    elements = [e for e in raw.mesh.elem if e[1] == 862 and e[2] == 861]
    elem = np.array([e[8] for e in elements])
    face_nodes = np.array([e[10:18][SIX] for e in elements])
    reference = raw.mesh.nodes[positions(raw.mesh.nnum, face_nodes)]
    displacement = field[positions(ids, face_nodes)]

    def gaps(x):
        p = np.einsum("ng,fnk->fgk", SHAPE, x).reshape(-1, 3)
        local = pilot + rotation.inv().apply(p - pilot - shift)
        return distances(local).reshape(-1, 3), local.reshape(-1, 3, 3)

    moved, body = gaps(reference + displacement)
    before, _ = gaps(reference)
    enum, vals, _ = raw.element_solution_data(number - 1, "EMN")
    forces = np.zeros((len(elem), 3))
    for j, k in enumerate(positions(enum, elem)):
        record = vals[k]
        if record is not None and len(record):
            forces[j] = record[42:45]
    actual = np.linalg.norm(forces, axis=1) > 1e-8
    geometry = (moved < -1e-8).any(1)
    reported = proof["states"][number - 1]["both_contact_pairs"]["861"]
    np.testing.assert_allclose(forces.sum(0), reported["force_N"], rtol=1e-6, atol=1e-7)
    (j,) = np.flatnonzero(elem == onset["case_contact_element"])
    k = onset["point"] - 1
    check = independent_distance(body[j, k], tri)
    assert abs(check - moved[j, k]) < 1e-8
    return {
        "native_set": number,
        "registered_cased_travel_mm": float(shift[0]),
        "rigid_pose_fit_error_mm": error,
        "originally_predicted_element": int(elem[j]),
        "originally_predicted_point": int(k + 1),
        "signed_gap_with_native_cell_pose_and_fixed_PLA_mm": float(before[j, k]),
        "signed_gap_with_native_cell_pose_and_deformed_PLA_mm": float(moved[j, k]),
        "signed_gap_independent_triangle_check_mm": check,
        "originally_predicted_face_force_N": forces[j].tolist(),
        "native_faces_with_force": int(actual.sum()),
        "intersecting_faces_in_deformed_pose": int(geometry.sum()),
        "common_faces": int(np.count_nonzero(actual & geometry)),
        "sum_native_contact_force_N": forces.sum(0).tolist(),
    }


def run():
    input_hashes = primary_inputs()
    raw, grids, distances, tri, proof, max_u = native_fixture()
    old_path = AUDIT / "bare_pull_poses_in_case.json"
    original = read(old_path)
    rows = {}
    for direction, name in [
        ("positive_X", "lateral_friction_locked"),
        ("negative_X", "lateral_friction_locked_minus"),
    ]:
        pilot, h, poses, source = bare_poses(name)
        known = original["directions"][direction]
        assert (
            source["rst_sha256"] == known["rst_sha256"]
            and source["pose_readback_sha256"] == known["pose_readback_sha256"]
        )
        stop = abs(known["signed_travel_bracket_mm"][-1])
        out = {}
        gmsh.initialize()
        try:
            gmsh.option.setNumber("General.Terminal", 0)
            cad_source = read(AUDIT / "local_rigid_side_clearance.json")
            verified(old, cad_source["hardware_STEP_sha256"])
            verified(STEP, STEP_HASH)
            out["CAD_linear_pose"] = cad_onset(
                BarePath(direction, "linear", pilot, h, poses),
                stop,
                cad_source["initial_left_cell_gap_mm"],
            )
        finally:
            gmsh.finalize()
        for size, (pts, labels, ids) in grids.items():
            radius = np.linalg.norm(pts - pilot, axis=1).max() + 1.0
            d0 = distances(pts)
            checks = {}
            for method in ("linear", "pchip"):
                path = BarePath(direction, method, pilot, h, poses)
                knots = path.travel[path.travel < stop].tolist() + [stop]
                assert max(np.linalg.norm(path.at(x)[:3], ord=1) for x in knots) < 1.0
                # Outside this enclosure no point can reach the target before the final load.
                motion = sum(path.motion_bound(a, b, radius) for a, b in itertools.pairwise(knots))
                lock_distances = distances(path.inverse(pts, 0))
                near = np.flatnonzero(lock_distances <= motion + 1e-5)
                assert len(near) > 0 and lock_distances.min() > 0

                def gap(x, path=path, selected=pts[near]):
                    return float(distances(path.inverse(selected, x)).min())

                result = first_contact(path, gap, radius, stop)
                loc = {}
                for label, travel in zip(
                    ("clear", "touch"), result["travel_magnitude_mm"], strict=True
                ):
                    pos = path.inverse(pts[near], travel)
                    values = distances(pos)
                    j = int(np.argmin(values))
                    i = int(near[j])
                    independent = independent_distance(pos[j], tri)
                    assert abs(independent - values[j]) < 1e-8, (independent, values[j])
                    loc[label] = {
                        "case_STEP_face": int(labels[i]),
                        "case_xyz_mm": pts[i].tolist(),
                        "signed_check_mm": independent,
                        "point": int(i % 3 + 1),
                    }
                    if ids is not None:
                        loc[label]["case_contact_element"] = int(ids[i])
                assert loc["clear"]["signed_check_mm"] > 0 and loc["touch"]["signed_check_mm"] < 0
                result["witness"] = loc
                checks[method] = result
                print(
                    direction,
                    size,
                    method,
                    result["travel_magnitude_mm"],
                    result["bare_reaction_N"],
                    flush=True,
                )
            out[size] = {"checks": checks, "initial_gap_mm": float(d0.min()), "total_points": len(pts)}
        if direction == "positive_X":
            lock = proof["first_loaded_moving_cell_bracket"]
            cases = proof["states"]
            bare = [(row["set"], row["ux_mm"], row["fx_N"]) for row in h]
            discrepancies = []
            for r in cases[: lock[0]["native_set"]]:
                k = r["native_set"]
                idx = int(k) - 1
                assert r["both_contact_pairs"]["861"]["loaded_corners"] == 0 and bare[idx][0] == k
                assert abs(bare[idx][1] - r["travel_mm"]) < 1e-8
                discrepancies.append(abs(bare[idx][2] - r["cell_force_N"]))
            assert max(discrepancies) < 1e-5
            saved = out["native_1.5_mm"]["checks"]["linear"]["travel_magnitude_mm"]
            assert lock[0]["travel_mm"] < saved[0] < saved[1] < lock[1]["travel_mm"]
            out["native_check"] = {
                "bracket": lock,
                "max_precontact_cell_force_difference_N": max(discrepancies),
                "checked_unloaded_states": len(discrepancies),
            }
            out["native_check"]["subsequent_loaded_pose"] = native_first_loaded_pose(
                raw,
                proof,
                distances,
                tri,
                pilot,
                out["native_1.5_mm"]["checks"]["linear"]["witness"]["touch"],
            )
        rows[direction] = {
            "bare_rst_sha256": source["rst_sha256"],
            "bare_pose_sha256": source["pose_readback_sha256"],
            "native_bare_force_bracket_N": known["bare_force_at_bracketing_states_N"],
            "meshes": out,
        }
    recorded = proof["initial_contact_search"]["pairs"]["861"]["gap_mm"]
    assert abs(rows["positive_X"]["meshes"]["native_1.5_mm"]["initial_gap_mm"] - recorded) < 1e-6
    write_json(
        AUDIT / "directional_first_contact.json",
        {
            "case": CASE,
            "campaign": CAMPAIGN,
            "native_STEP_sha256": STEP_HASH,
            "sealed_primary_input_sha256": input_hashes,
            "earlier_CAD_check_sha256": digest(old_path),
            "checkpoint_sha256": digest(AUDIT / f"{CASE}_ls3_ss12_checkpoint.json"),
            "fine_local_mesh_sha256": digest(MESH / "case_1.5.npz"),
            "coarse_local_mesh_sha256": digest(MESH / "case_3.npz"),
            "rigid_target_sha256": digest(MESH / "fixture_targets_0005.npz"),
            "native_unloaded_max_case_motion_mm": max_u,
            "directions": rows,
            "scope": "First entry of a Gauss point on a left-pocket contact triangle into the rigid faceted battery. "
            "The stationary case and interpolated bare-fixture poses describe the path up to first contact. Forces are interpolated bare reactions.",
        },
    )


if __name__ == "__main__":
    run()

"""Check the pressure implied by prescribed middle-pocket poses against archived static ANSYS forces."""

import argparse

import numpy as np
from case_stress import source
from dpf_readback import export
from film_identity import digest, verified, write_json
from snug_board_pull import AUDIT, CAMPAIGN, positions, read
from snug_contact_startup import exact_check
from snug_contact_vibration import BRANCHES, CACHE, coordinates
from snug_pocket_faces import BARYCENTRIC, SHAPE
from snug_pocket_sampling import candidates, groups, project, shape


def predicted(caps, targets, case, cell, cell0, axis, radius, kn):
    """Independent normal-penalty check at a fixed configuration; forces in N, mesh coordinates in mm."""
    points = np.einsum("ng,fnk->fgk", SHAPE, case).reshape(-1, 3)
    gp, face = candidates(
        points, np.full(len(points), 1e-8), cell, np.zeros(cell.shape[:2]), axis, radius, cell0
    )
    gap, ok, uv = project(points[gp], cell[face], cell0[face], axis, radius, False)
    penetrating = np.flatnonzero(ok & (gap < -1e-9))
    # At a shared target edge, take the outermost radial intersection once.
    picked = {}
    for i in penetrating:
        if gp[i] not in picked or gap[i] < gap[picked[gp[i]]]:
            picked[gp[i]] = i
    take = np.array(sorted(picked.values()), int)
    _, du, dv = shape(BARYCENTRIC[:, :2])
    area = np.linalg.norm(np.cross(du @ case, dv @ case), axis=2) / 6
    forces = np.zeros((len(case), 3))
    rows = []
    if len(take):
        _, u, v = shape(uv[take])
        t = cell[face[take]]
        normal = np.cross(np.einsum("ij,ijk->ik", u, t), np.einsum("ij,ijk->ik", v, t))
        normal /= np.linalg.norm(normal, axis=1)[:, None]
        radial = points[gp[take]][:, [0, 2]] - axis.xz
        radial /= np.linalg.norm(radial, axis=1)[:, None]
        cosine = np.einsum("ij,ij->i", normal[:, [0, 2]], radial)
        normal *= np.sign(cosine)[:, None]
        assert min(abs(cosine)) > 0.99
        for i, n, cos in zip(take, normal, abs(cosine), strict=True):
            group, j = divmod(gp[i], 3)
            pressure = kn[group] * (-gap[i] * 1e-3) * cos
            assert np.isfinite(pressure) and pressure > 0, (kn[group], group)
            f = pressure * area[group, j] * 1e-6
            forces[group] += f * n
            rows.append(
                {
                    "element": int(caps[group]),
                    "point": int(j + 1),
                    "target": int(targets[face[i]]),
                    "radial_penetration_um": float(-1000 * gap[i]),
                    "pressure_MPa": float(pressure / 1e6),
                    "normal_force_N": float(f),
                    "point_xyz_mm": points[gp[i]].tolist(),
                    "from_low_Y_barrel_end_mm": float(points[gp[i], 1] - cell0[:, :, 1].min()),
                    "direction": n.tolist(),
                    "reference_stiffness_N_per_m3": float(kn[group]),
                    "integration_area_mm2": float(area[group, j]),
                }
            )
    return forces, rows, area


def stiffness_and_force(raw, k, caps):
    numbers, records, _ = raw.element_solution_data(k, "EMN")
    sel = positions(numbers, caps)
    kn = np.zeros(len(caps))
    net = np.zeros((len(caps), 3))
    for i, ix in enumerate(sel):
        record = records[ix]
        if record is None or not len(record):
            continue
        assert len(record) >= 45
        v = record[24:28]
        positive = v[v > 0]
        assert np.isfinite(v).all() and min(v) >= 0
        if len(positive):
            assert np.ptp(positive) < max(1.0, 1e-6 * v.max()), v
        # Only use faces carrying a consistent KN at all four recorded corner slots.
        kn[i] = v[0] if len(positive) == 4 else 0.0
        net[i] = -record[42:45]
    return kn, net


def run(branch):
    bp = AUDIT / f"{branch}_contact_vibration_basis.json"
    br = read(bp)
    cache = CACHE / (branch + "_basis") / f"coupled_contact_b{br['residual_blocks']}"
    verified(cache / "basis.npz", br["basis_sha256"])
    with np.load(cache / "basis.npz") as f:
        data = {k: f[k] for k in f.files}
    (cap, target), static = groups(branch, data)
    caps, face_ids, case0, _, _ = cap
    targets, cell_ids, cell0, ctr, radius = target
    # Retrieve KN and static CNF directly from the nominal output repeat and the native fine model.
    controls = (
        "snug125_nylon_mesh15_static" if branch.endswith("mesh15") else "snug125_nylon_out2_static"
    )
    proof, _folder, raw = source(controls, CAMPAIGN)
    frames = []
    all_indices = np.unique(np.r_[face_ids.ravel(), cell_ids.ravel()])
    ids = data["nodes"][all_indices]
    initial = 1000 * raw.mesh.nodes[positions(raw.mesh.nnum, ids)]
    case_rows = positions(all_indices, face_ids)
    cell_rows = positions(all_indices, cell_ids)
    np.testing.assert_allclose(initial[case_rows], case0, atol=2e-8, rtol=0)
    np.testing.assert_allclose(initial[cell_rows], cell0, atol=2e-8, rtol=0)
    if branch != "snug125_aluminium":
        sets = list(range(1, raw.nsets + 1))
        fields = export(controls, CAMPAIGN, sets)
        for step in sets:
            stem = fields / f"set_{step:04d}"
            n = np.fromfile(stem.with_suffix(".ids"), "<i4")
            order = np.argsort(n)
            u = np.fromfile(stem.with_suffix(".u"), "<f8").reshape(-1, 3)[
                order[positions(n[order], ids)]
            ]
            xyz = initial + 1000 * u
            kn, native = stiffness_and_force(raw, step - 1, caps)
            force, rows, _areas = predicted(
                caps, targets, xyz[case_rows], xyz[cell_rows], cell0, ctr, radius, kn
            )
            expected = np.linalg.norm(native, axis=1) > 1e-8
            observed = np.linalg.norm(force, axis=1) > 1e-8
            error = float(np.linalg.norm(force - native))
            frames.append(
                {
                    "native_set": step,
                    "time": float(raw.time_values[step - 1]),
                    "displacement_sha256": digest(stem.with_suffix(".u")),
                    "native_net_N": float(np.linalg.norm(native.sum(0))),
                    "reconstructed_net_N": float(np.linalg.norm(force.sum(0))),
                    "native_faces": caps[expected].tolist(),
                    "geometry_faces": caps[observed].tolist(),
                    "face_vector_mismatch_N": error,
                    "largest_individual_face_error_N": float(
                        np.linalg.norm(force - native, axis=1).max()
                    ),
                    "points": rows,
                }
            )
            print(
                branch,
                "set",
                step,
                np.count_nonzero(expected),
                np.count_nonzero(observed),
                frames[-1]["native_net_N"],
                frames[-1]["reconstructed_net_N"],
                error,
                flush=True,
            )
    if frames:
        assert len(frames) == 8 and np.array_equal([r["native_set"] for r in frames], np.arange(1, 9))
        for r in frames:
            assert set(r["geometry_faces"]) <= set(r["native_faces"])
            if r["native_net_N"] == 0:
                assert r["reconstructed_net_N"] == 0
        for r in frames[-3:]:
            assert r["geometry_faces"] == r["native_faces"] and r["face_vector_mismatch_N"] < 0.0002
    book = AUDIT / f"{branch}_spacer_pocket_pull.json"
    base = read(book)
    kn, _ = stiffness_and_force(raw, raw.nsets - 1, caps)
    _, du, dv = shape(BARYCENTRIC[:, :2])
    locked = 1000 * data["positions"][face_ids]
    area = np.linalg.norm(np.cross(du @ locked, dv @ locked), axis=2) / 6
    errors = []
    for label, k in zip(
        base["contact_labels"][:-4], base["compression_slope_N_per_m"][:-4], strict=True
    ):
        e, j = map(int, label.split("."))
        i = positions(caps, [e])[0]
        errors.append(float((kn[i] * area[i, j - 1] * 1e-6) / k - 1))
    assert max(abs(x) for x in errors) < 0.001, errors
    history = read(AUDIT / f"{branch}_contact_vibration.json")
    matched = read(AUDIT / "matched_contact_startup.json")
    sample = matched["axes"]["Y"]["station"]
    h = cache / "Y_history.npz"
    verified(h, history["axes"]["Y"]["history_sha256"])
    with np.load(h) as f:
        a = f["load"][: sample + 1]
    o, B, drive, T = coordinates(data, br["residual_blocks"])
    q, _ = exact_check(o, B, data["k"], data["g"], drive[:, 1], a, 4)
    n = br["native_modes"]
    pose = np.r_[q[-1, :n], T @ q[-1, n:]]
    mesh = 1000 * (
        data["positions"][all_indices] + np.einsum("ijk,k->ij", data["skin"][all_indices], pose)
    )
    force, rows, _ = predicted(caps, targets, mesh[case_rows], mesh[cell_rows], cell0, ctr, radius, kn)
    report = {
        "branch": branch,
        "case": controls,
        "static_kn_source_rst_sha256": proof["rst_sha256"],
        "original_static_rst_sha256": static["rst_sha256"],
        "startup_basis_sha256": br["basis_sha256"],
        "matched_pose_sha256": digest(AUDIT / "matched_contact_startup.json"),
        "lock_matrix_check_sha256": digest(book),
        "relative_locked_point_stiffness_errors": errors,
        "installation": frames,
        "matched_base_Y": {
            "sample": sample,
            "time_ms": sample / 65.536,
            "total_N": float(np.linalg.norm(force.sum(0))),
            "force_on_case_XYZ_N": force.sum(0).tolist(),
            "points": rows,
        },
        "scope": "Independent prescribed-pose estimate on cylindrical target faces. KN is the archived normal penalty stiffness. Aluminium uses the nominal nylon KN, checked against its own locked contact matrix. Reactions at newly reached points have not been coupled back into the motion.",
    }
    write_json(AUDIT / (branch + "_prescribed_contact_check.json"), report)
    print(branch, "prescribed Y", report["matched_base_Y"]["total_N"], len(rows), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("branch", choices=BRANCHES)
    run(p.parse_args().branch)

"""Trace spacer seating and middle-pocket compression when all four M4 shanks are shortened equally."""

import numpy as np
from early_cell_clearance import bezier, outer_faces
from film_identity import digest, write_json
from snug_board_pull import AUDIT, BODIES, positions, read
from snug_board_tangent import symmetric_product
from snug_cellpush_geometry import swept_points
from snug_pocket_faces import SHAPE
from snug_pocket_sampling import groups
from snug_spacer_bearing import PILOTS
from snug_tab_pocket_pull import segments


def geometry(branch, raw, dofs, free, transfer, Y, labels):
    mid = outer_faces(raw, [BODIES[1]])
    (cap, _), _ = groups(branch, {"nodes": raw.mesh.nnum, "middle": positions(raw.mesh.nnum, mid)})
    elem, face_rows, _, _, _ = cap
    src = raw.mesh.nnum[face_rows]
    ids = np.unique(np.r_[src.ravel(), mid.ravel(), PILOTS])
    x = raw.mesh.nodes[positions(raw.mesh.nnum, ids)] * 1000
    equation = 8 * dofs[:, 0].astype(np.int64) + dofs[:, 1]
    order = np.argsort(equation)
    idx = order[positions(equation[order], 8 * ids[:, None] + np.arange(3))]
    sparse_u = np.zeros((len(dofs), Y.shape[1]))
    sparse_u[free] = Y
    field = 1000 * (sparse_u + transfer @ sparse_u)[idx]
    keys = [(int(e), j) for e in elem for j in (1, 2, 3)]
    active = {tuple(map(int, s.split("."))) for s in labels[:-4]}
    open_rows = [i for i, key in enumerate(keys) if key not in active]
    assert len(open_rows) + len(active) == len(keys)
    start = np.einsum("ng,fnc->fgc", SHAPE, x[positions(ids, src)]).reshape(-1, 3)[open_rows]
    modes = np.einsum("ng,fncm->fgcm", SHAPE, field[positions(ids, src)]).reshape(len(keys), 3, -1)[open_rows]
    ix = positions(ids, mid)
    # Express target geometry in the same six-control Bernstein basis as the checked side-pull sweeps.
    initial = bezier(x[ix])
    motion = bezier(field[ix].transpose(0, 3, 1, 2)).transpose(0, 2, 3, 1)
    return (
        start,
        modes,
        initial,
        motion,
        [keys[i] for i in open_rows],
        x[positions(ids, PILOTS)],
        field[positions(ids, PILOTS)],
    )


def check(branch, raw, dofs, free, transfer, labels, k, g, C, Y, B, K, cell, cell_u, seats, identity):
    old_path = AUDIT / f"{branch}_spacer_sensitivity.json"
    earlier = read(old_path)
    loading = read(AUDIT / f"{branch}_spacer_pocket_pull.json")
    assert loading["contact_labels"] == labels and loading["full_files"] == identity["files"]
    assert earlier["basis_rst_sha256"] == loading["modal_rst_sha256"]
    np.testing.assert_allclose(
        C[-4:, -4:], earlier["relative_separation_compliance_m_per_N"], rtol=2e-8, atol=1e-16
    )
    kb = np.array(seats["beam_stiffness_N_per_m"])
    installed = np.array(seats["beam_direct_force_N"])
    normal = np.array(seats["bearing_direction_at_lock"])
    drive = np.r_[np.zeros(len(k) - 4), kb] * 1e-6
    slope = C @ drive
    target_mean_N = 1.0
    # Use micrometres for the path parameter. All compliance and signed gap calculations use SI units.
    upper_um = 1.0
    xp, pm, face, fm, point_ids, pilot0, pilot = geometry(branch, raw, dofs, free, transfer, Y, labels)
    base_comp = 1e6 * cell.T @ cell_u
    before = read(AUDIT / f"{branch}_full_board_tangent.json")
    np.testing.assert_allclose(base_comp, before["cell_X_um_per_N"], atol=1e-7)
    rows = []
    for lo, hi, active, diff, offset, intercept, rate in segments(C, slope, k, g, upper_um):

        def state(t, intercept=intercept, rate=rate, diff=diff, offset=offset):
            advance = intercept + rate * t
            reaction = offset + diff * advance
            weight = t * drive - reaction
            compression = k * np.maximum(0, g + advance)
            tension = installed + kb * (t * 1e-6 - advance[-4:])
            return weight, compression, tension

        a, ca, ta = state(lo)
        b, cb, tb = state(hi)
        assert tb.mean() > ta.mean()
        if tb.mean() >= target_mean_N:
            hi = lo + (hi - lo) * (target_mean_N - ta.mean()) / (tb.mean() - ta.mean())
            b, cb, tb = state(hi)
        point0, point1 = xp + pm @ a, xp + pm @ b
        face0, face1 = face + fm @ a, face + fm @ b
        counts, hits, unresolved = swept_points(point0, point1, face0, face1)
        if unresolved:
            raise ValueError(f"Unresolved contact-point pairs on {branch} at {lo}–{hi} um: {unresolved[:4]}")
        hit = None
        if hits:
            item = min(hits, key=lambda r: r["load_fraction"])
            t = lo + (hi - lo) * item["load_fraction"]
            # Certify separation up to a value below the attained crossing.
            prior = max(lo, t - 0.001 * (hi - lo))
            u, _, _ = state(prior)
            _, roots, pending = swept_points(point0, xp + pm @ u, face0, face + fm @ u)
            assert not roots and not pending
            hit = {
                "element": point_ids[item["point_index"]][0],
                "point": point_ids[item["point_index"]][1],
                "shortening_bracket_um": [prior, t],
                "coincidence_error_mm": item["coincidence_error_mm"],
            }
            hi = t
            b, cb, tb = state(hi)
        disp = Y @ b
        delta = B.T @ disp
        np.testing.assert_allclose(delta, intercept + rate * hi, rtol=1e-7, atol=2e-14)
        residual = symmetric_product(K, disp[:, None])[:, 0] - B @ b
        assert np.linalg.norm(residual) < 2e-6
        pilot_xyz = (pilot0 + pilot @ b).reshape(4, 2, 3) * 1e-3
        length = np.linalg.norm(np.diff(pilot_xyz, axis=1)[:, 0], axis=1)
        before_length = np.linalg.norm(np.diff(pilot0.reshape(4, 2, 3), axis=1)[:, 0], axis=1) * 1e-3
        projection = np.einsum("ij,ij->i", np.diff((pilot @ b).reshape(4, 2, 3), axis=1)[:, 0], normal) * 1e-3
        np.testing.assert_allclose(projection, -delta[-4:], atol=1e-14)
        err = float(max(abs(length - before_length + delta[-4:])) * 1e9)
        assert err < 0.01
        # Tangent with the bearing set inside this interval, independently checked against the unreduced equations.
        z = np.linalg.solve(np.eye(len(k)) + C * diff, B.T @ cell_u)
        tang = cell_u - Y @ (diff[:, None] * z)
        tangent_residual = symmetric_product(K, tang) + B @ (diff[:, None] * (B.T @ tang)) - cell
        assert max(np.linalg.norm(tangent_residual, axis=0)) < 3e-6
        matrix = 1e6 * cell.T @ tang
        np.testing.assert_allclose(matrix, matrix.T, atol=1e-8)
        if not rows:
            np.testing.assert_allclose(matrix, base_comp, atol=1e-7)
        else:
            np.testing.assert_allclose(rows[-1]["shank_tension_N"], ta, atol=5e-8)
            np.testing.assert_allclose(rows[-1]["pocket_and_spacer_N"], ca, atol=5e-8)
        rows.append(
            {
                "shortening_interval_um": [lo, hi],
                "bearing_inside_interval": [s for s, bearing in zip(labels, active, strict=True) if bearing],
                "pocket_and_spacer_N": cb.tolist(),
                "middle_pocket_compression_N": float(cb[:-4].sum()),
                "shank_tension_N": tb.tolist(),
                "mean_shank_tension_N": float(tb.mean()),
                "cell_X_displacement_um": (1e6 * cell.T @ disp).tolist(),
                "cell_X_compliance_um_per_N": matrix.tolist(),
                "finite_spacer_length_error_nm": err,
                "new_point": hit,
                "unresolved_hull_pairs_per_depth": counts,
                "full_system_residual_N": float(np.linalg.norm(residual)),
            }
        )
        if hit or np.isclose(tb.mean(), target_mean_N, rtol=1e-10):
            break
    assert rows and (
        rows[-1]["new_point"] or np.isclose(rows[-1]["mean_shank_tension_N"], target_mean_N, rtol=1e-10)
    )
    record = {
        "branch": branch,
        "native_modal_rst_sha256": loading["modal_rst_sha256"],
        "previous_spacer_sensitivity_sha256": digest(old_path),
        "coupled_static_audit_sha256": digest(AUDIT / f"{branch}_spacer_pocket_pull.json"),
        "labels": labels,
        "starting_shank_tension_N": installed.tolist(),
        "starting_pocket_and_spacer_N": (k * np.maximum(0, g)).tolist(),
        "locked_cell_X_compliance_um_per_N": base_comp.tolist(),
        "target_mean_shank_tension_N": target_mean_N,
        "open_gauss_stations": len(point_ids),
        "middle_cell_target_triangles": len(face),
        "intervals": rows,
        "scope": "Independent incremental whole-board equilibrium with equally shortened M4 shanks, unilateral "
        "spacers and initially loaded middle-pocket points. The 1 N mean shank tension is a sensitivity "
        "target. All initially open middle-pocket stations are checked over the full path. Other contact "
        "interfaces and geometric stiffness retain their installed linearization. Physical screw torque "
        "and preload were not supplied.",
    }
    write_json(AUDIT / f"{branch}_screw_preload_path.json", record)
    print(
        branch,
        [
            (
                r["shortening_interval_um"],
                r["mean_shank_tension_N"],
                r["middle_pocket_compression_N"],
                r["new_point"],
            )
            for r in rows
        ],
        flush=True,
    )

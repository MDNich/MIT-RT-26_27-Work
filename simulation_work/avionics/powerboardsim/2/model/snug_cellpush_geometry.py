"""Check continuous contact-point paths on the middle cell during the whole-board +X load."""

import numpy as np
from early_cell_clearance import bezier, outer_faces, subdivision_weights
from film_cell_contact import TOL_MM, candidate_pairs
from film_identity import digest, write_json
from installed_cell_gap import target_connectivity
from scipy.optimize import root
from snug_board_pull import AUDIT, BODIES, REGISTRY, positions, read
from snug_outer_witness import basis
from snug_pocket_faces import SHAPE
from snug_pocket_sampling import candidates, groups, project, shape
from snug_tab_pocket_pull import segments


def remaining(a, b, clearance):
    """Separate the origin from the convex hull of the twelve relative Bernstein controls."""
    low = np.minimum(a.min(1), b.min(1))
    high = np.maximum(a.max(1), b.max(1))
    keep = np.flatnonzero(np.linalg.norm(np.maximum(0, np.maximum(low, -high)), axis=1) <= clearance)
    for polygon in (a, b):
        tri = polygon[keep, :3]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1)[:, None], 1e-30)
        v = np.einsum("nfj,nj->nf", a[keep], n)
        w = np.einsum("nfj,nj->nf", b[keep], n)
        gap = np.maximum(np.minimum(v.min(1), w.min(1)), -np.maximum(v.max(1), w.max(1)))
        keep = keep[gap <= clearance]
    return keep


def intersection(a, b):
    """Return an actual point on the quadratic target and inside the applied-load interval."""

    def equation(q):
        u, v, t = q
        return basis([u, v, 1 - u - v]) @ (a + t * (b - a))

    solution = root(equation, [1 / 3, 1 / 3, 0.5], tol=1e-11)
    u, v, t = solution.x
    residual = np.linalg.norm(equation(solution.x))
    if residual > 1e-10 or not np.isfinite(residual) or min(u, v, 1 - u - v, t, 1 - t) < 0:
        return None
    return {
        "target_barycentric": [u, v, 1 - u - v],
        "load_fraction": t,
        "coincidence_error_mm": residual,
    }


def swept_points(p0, p1, t0, t1, clearance=TOL_MM):
    """Enclose all intermediate loads using the affine endpoints on one bearing interval."""
    point, face = candidate_pairs(
        (np.minimum(p0, p1) - clearance, np.maximum(p0, p1) + clearance),
        (np.minimum(t0.min(1), t1.min(1)), np.maximum(t0.max(1), t1.max(1))),
    )
    a0, b0 = t0[face] - p0[point, None], t1[face] - p1[point, None]
    a, b = a0, b0
    pairs = np.arange(len(a))
    child = subdivision_weights()
    counts, hits = [], []
    for depth in range(14):
        keep = remaining(a, b, clearance)
        a, b, pairs = a[keep], b[keep], pairs[keep]
        counts.append(len(a))
        if not len(a):
            break
        if depth == 4:
            confirmed = []
            for i in np.unique(pairs):
                crossing = intersection(a0[i], b0[i])
                if crossing is not None:
                    hits.append(dict(point_index=int(point[i]), target_index=int(face[i]), **crossing))
                    confirmed.append(i)
            rest = ~np.isin(pairs, confirmed)
            a, b, pairs = a[rest], b[rest], pairs[rest]
            if not len(a):
                break
        if depth == 13 or len(a) > 50000:
            break
        a = (child @ a[:, None]).reshape(-1, 6, 3)
        b = (child @ b[:, None]).reshape(-1, 6, 3)
        pairs = np.repeat(pairs, 4)
    pending = sorted({(int(point[i]), int(face[i])) for i in pairs})
    return counts, hits, pending


def clearance_bound(points, cells, barrel, open_ids, point_ids, loads):
    """Bracket the smallest space-time distance using attained endpoints and swept convex hulls."""
    targets, select, cell0, axis, radius = barrel
    best = None
    for pts, skin, load in zip(points, cells, loads, strict=True):
        # Recover the actual six Lagrange sites from this target's Bernstein controls.
        tri = skin[select].copy()
        tri[:, 3:] = 0.5 * tri[:, 3:] + 0.25 * (tri[:, :3] + np.roll(tri[:, :3], -1, axis=1))
        gi, fi = candidates(pts, np.zeros(len(pts)), tri, np.zeros(tri.shape[:2]), axis, radius, cell0)
        gap, ok, uv = project(pts[gi], tri[fi], cell0[fi], axis, radius, False)
        ix = np.flatnonzero(ok)
        if not len(ix):
            raise ValueError("No cylindrical witness for the left-cell load")
        j = ix[np.argmin(abs(gap[ix]))]
        w, _, _ = shape(uv[j : j + 1])
        delta = pts[gi[j]] - w[0] @ tri[fi[j]]
        distance = np.linalg.norm(delta)
        assert abs(distance - abs(gap[j])) < 1e-8
        if best is None or distance < best["distance_mm"]:
            elem, point = point_ids[open_ids[gi[j]]]
            best = {
                "distance_mm": distance,
                "applied_force_N": load,
                "case_element": elem,
                "point": point,
                "cell_target": int(targets[fi[j]]),
                "target_uv": uv[j].tolist(),
            }
    # Test the complete closed middle cell, including ends. A successful test excludes every
    # allowed point/face pair over the entire load range, regardless of the location of the witness.
    p0, p1 = points
    t0, t1 = cells
    upper = best["distance_mm"] + TOL_MM
    i, j = candidate_pairs(
        (np.minimum(p0, p1) - upper, np.maximum(p0, p1) + upper),
        (np.minimum(t0.min(1), t1.min(1)), np.maximum(t0.max(1), t1.max(1))),
    )
    a0 = t0[j] - p0[i, None]
    b0 = t1[j] - p1[i, None]
    child = subdivision_weights()
    lower = 0.0
    for fraction in (0.995, 0.98, 0.9, 0.75, 0.5, 0.25, 0.1):
        trial = fraction * best["distance_mm"]
        a, b = a0, b0
        for depth in range(12):
            keep = remaining(a, b, trial + TOL_MM)
            if not len(keep):
                lower = trial
                break
            if depth >= 7 and len(keep) > 800:
                break
            a = (child @ a[keep, None]).reshape(-1, 6, 3)
            b = (child @ b[keep, None]).reshape(-1, 6, 3)
        if lower:
            break
    return {
        "certified_lower_nm": 1e6 * lower,
        "attained_upper_nm": 1e6 * best["distance_mm"],
        "witness": best,
    }


def check(branch, raw, dofs, free, transfer, labels, k, g, compliance, cell_slope, Y, cell_u, identity):
    other = read(AUDIT / (branch + "_spacer_pocket_pull.json"))
    assert other["full_files"] == identity["files"] and other["contact_labels"] == labels
    actual = read(REGISTRY)[branch.removesuffix("_mesh15") + "_cellpush_x"]
    endpoint = actual["endpoint_force_N"]
    middle = outer_faces(raw, [BODIES[1]])
    data = {"nodes": raw.mesh.nnum, "middle": positions(raw.mesh.nnum, middle)}
    (case, barrel), static = groups(branch, data)
    caps, facets, _, _, _ = case
    sources = raw.mesh.nnum[facets]
    targets = target_connectivity(raw)
    # Use the complete cell boundary, including its ends, in the continuous crossing check.
    lookup = {
        tuple(sorted(v[i] for i in (0, 1, 2, 4, 5, 7))): e for e, v in targets.items() if v[2] == v[3]
    }
    target_ids = np.array([lookup[tuple(sorted(f))] for f in middle])
    # Reorder the reference cylinder nodes to match the target skin used for the witness. The boundary connectivity
    # from outer_faces can list the same triangle with a different winding.
    b_ids, b_sites, b_original, b_axis, radius = barrel
    b_nodes = raw.mesh.nnum[b_sites]
    order_targets = np.argsort(target_ids)
    selected = order_targets[positions(target_ids[order_targets], b_ids)]
    native_slots = np.argmax(middle[selected, :, None] == b_nodes[:, None, :], axis=1)
    assert np.array_equal(np.take_along_axis(middle[selected], native_slots, axis=1), b_nodes)
    inverse_slots = np.argsort(native_slots, axis=1)
    b_original = np.take_along_axis(b_original, inverse_slots[:, :, None], axis=1)
    radial = (b_ids, selected, b_original, b_axis, radius)
    all_nodes = np.unique(np.r_[sources.ravel(), middle.ravel()])
    x = 1000 * raw.mesh.nodes[positions(raw.mesh.nnum, all_nodes)]
    si, ti = positions(all_nodes, sources), positions(all_nodes, middle)
    keys = 8 * dofs[:, 0].astype(np.int64) + dofs[:, 1]
    order = np.argsort(keys)
    ix = order[positions(keys[order], 8 * all_nodes[:, None] + np.arange(3))]

    def mapped(loads):
        full = np.zeros((len(dofs), loads.shape[1]))
        full[free] = loads
        return 1000 * (full + transfer @ full)[ix]

    port_u = mapped(Y)
    single_u = mapped(cell_u[:, None])[:, :, 0]
    active = {tuple(map(int, label.split("."))) for label in labels[:-4]}
    assert len(active) == len(g) - 4 and np.all(g[:-4] > 0)
    point_ids = [(int(e), j) for e in caps for j in (1, 2, 3)]
    open_ids = [i for i, p in enumerate(point_ids) if p not in active]
    assert len(open_ids) + len(active) == len(point_ids)
    previous = None
    intervals = []
    for lo, hi, bearing, diff, offset, intercept, rate in segments(
        compliance, cell_slope, k, g, endpoint
    ):
        fields = []
        for load in (lo, hi):
            change = offset + diff * (intercept + rate * load)
            xyz = x + load * single_u - port_u @ change
            fields.append(xyz)
        if previous is not None:
            np.testing.assert_allclose(previous, fields[0], atol=1e-9, rtol=0)
        previous = fields[1]
        points = [np.einsum("ng,fnk->fgk", SHAPE, xyz[si]).reshape(-1, 3)[open_ids] for xyz in fields]
        cells = [bezier(xyz[ti]) for xyz in fields]
        counts, hits, unresolved = swept_points(*points, *cells)

        def identify(point, face):
            e, j = point_ids[open_ids[point]]
            return {"case_element": e, "point": j, "cell_target": int(target_ids[face])}

        for hit in hits:
            hit.update(identify(hit.pop("point_index"), hit.pop("target_index")))
            hit["applied_force_N"] = lo + (hi - lo) * hit["load_fraction"]
        intervals.append(
            {
                "load_range_N": [lo, hi],
                "bearing": [name for name, on in zip(labels, bearing) if on],
                "surviving_hull_pairs": counts,
                "confirmed_crossings": hits,
                "unresolved_pairs": [identify(i, j) for i, j in unresolved],
            }
        )
        if not hits and not unresolved:
            intervals[-1]["minimum_separation"] = clearance_bound(
                points, cells, radial, open_ids, point_ids, (lo, hi)
            )
        print(branch, lo, hi, "confirmed", len(hits), "unresolved", len(unresolved), flush=True)
    # Match the native lock's original point identities against the separately reconstructed contact geometry.
    pressure_path = AUDIT / (branch + "_prescribed_contact_check.json")
    control = read(pressure_path)
    assert control["original_static_rst_sha256"] == static["rst_sha256"]
    if control["installation"]:
        assert active == {(r["element"], r["point"]) for r in control["installation"][-1]["points"]}
    write_json(
        AUDIT / (branch + "_cellpush_swept_points.json"),
        {
            "branch": branch,
            "parent_rst_sha256": static["rst_sha256"],
            "whole_board_inputs_sha256": digest(REGISTRY),
            "spacer_pocket_prediction_sha256": digest(AUDIT / (branch + "_spacer_pocket_pull.json")),
            "pressure_check_sha256": digest(pressure_path),
            "endpoint_force_N": endpoint,
            "middle_pocket_triangles": len(caps),
            "cell_boundary_triangles": len(middle),
            "initially_unloaded_points": len(open_ids),
            "original_bearing_points": sorted(active),
            "geometry_tolerance_mm": TOL_MM,
            "intervals": intervals,
            "scope": "Independent +X left-cell loading along the piecewise-affine whole-board equilibrium. "
            "New intersections invalidate continuation with the original bearing set. Multiple roots on a "
            "confirmed target pair are possible. This check covers the three Gauss stations on the middle pocket.",
        },
    )

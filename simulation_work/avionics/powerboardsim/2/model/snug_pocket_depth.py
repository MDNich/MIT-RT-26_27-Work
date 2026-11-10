"""Bound the overlap of two registered quadratic FE faces along a common local normal."""

from contextlib import contextmanager
from math import factorial

import numpy as np
from early_cell_clearance import EDGES, bezier, subdivision_weights
from scipy.optimize import minimize
from snug_outer_witness import basis, normal

# Sub-nanometre enclosure in millimetres. All geometry is recentered before operating on it.
WIDTH = 0.5e-6
ROUND_OFF = 1e-10
TRIANGLE = np.concatenate((np.eye(3), (np.eye(3) + np.roll(np.eye(3), -1, axis=0)) / 2))
QUARTIC = np.array([(i, j, 4 - i - j) for i in range(5) for j in range(5 - i)])
SITES = QUARTIC / 4
MAP = np.stack([basis(p) for p in SITES])
COEFFICIENTS = np.stack(
    [
        np.prod(SITES**power, axis=1) * factorial(4) / np.prod([factorial(p) for p in power])
        for power in QUARTIC
    ],
    axis=1,
)
QUARTIC_INVERSE = np.linalg.inv(COEFFICIENTS)
CHILDREN = subdivision_weights()


def surface_at(face, uv, cylinder=None):
    p = np.r_[uv, 1 - uv.sum()]
    point = basis(p) @ face
    if cylinder is not None:
        radius, gain = cylinder
        point[2] += gain * (np.sqrt(radius**2 - point[3] ** 2) - point[4])
    return point[:3]


def surface_gradient(face, uv, cylinder=None):
    u, v = uv
    w = 1 - u - v
    g = (
        np.array(
            [
                [2 * u, 0, -2 * w, 2 * v, -2 * v, 2 * (w - u)],
                [0, 2 * v, -2 * w, 2 * u, 2 * (w - v), -2 * u],
            ]
        )
        @ face
    )
    if cylinder is not None:
        radius, gain = cylinder
        x = basis(np.r_[uv, w]) @ face[:, 3]
        g[:, 2] -= gain * (x / np.sqrt(radius**2 - x**2) * g[:, 3] + g[:, 4])
    return g[:, :3]


def feasible_depth(case, cell, cylinders):
    """A pair of interior surface points at the same tangential position supplies the lower bound."""

    def delta(x):
        return surface_at(cell, x[2:], cylinders[1]) - surface_at(case, x[:2], cylinders[0])

    def gradient(x):
        return np.vstack(
            (-surface_gradient(case, x[:2], cylinders[0]), surface_gradient(cell, x[2:], cylinders[1]))
        ).T

    margin = 1e-8
    triangle_jac = np.array([[-1.0, -1.0, 0.0, 0.0], [0.0, 0.0, -1.0, -1.0]])
    constraints = [
        {"type": "eq", "fun": lambda x: delta(x)[:2], "jac": lambda x: gradient(x)[:2]},
        {
            "type": "ineq",
            "fun": lambda x: 1 - margin - np.array([x[:2].sum(), x[2:].sum()]),
            "jac": lambda x: triangle_jac,
        },
    ]
    feasible = []
    for uv in ((1 / 3, 1 / 3), (0.08, 0.08), (0.84, 0.08), (0.08, 0.84)):
        result = minimize(
            lambda x: -delta(x)[2],
            [*uv, 1 / 3, 1 / 3],
            jac=lambda x: -gradient(x)[2],
            bounds=[(margin, 1 - margin)] * 4,
            constraints=constraints,
            method="SLSQP",
            options={"ftol": 1e-14, "maxiter": 200},
        )
        # Refine the 2D projection onto the target and require a strictly interior witness.
        x = result.x.copy()
        for _ in range(3):
            x[2:] -= np.linalg.solve(gradient(x)[:2, 2:], delta(x)[:2])
        if min(*x, 1 - x[:2].sum(), 1 - x[2:].sum()) > 0 and np.linalg.norm(delta(x)[:2]) < 1e-12:
            feasible.append((float(delta(x)[2]), x))
    assert feasible, "No common projected interior point found"
    depth, x = max(feasible, key=lambda item: item[0])
    return depth, x, float(np.linalg.norm(delta(x)[:2]))


def parabola(x):
    a, b = x[..., 0], x[..., 1]
    return np.stack([np.ones_like(a), a, b, a * a, a * b, b * b], axis=-1)


def residual_heights(faces, polynomial, cylinder, *, maximum):
    # For equal (x,y) this common quadratic cancels from the height difference.
    # z(u,v)-p(x(u,v),y(u,v)) is a polynomial of total degree at most four.
    points = MAP @ faces
    values = points[..., 2] - parabola(points) @ polynomial
    error = 0.0
    if cylinder is not None:
        radius, gain = cylinder
        xs = faces[:, :, 3]
        mid = (xs.max(1) + xs.min(1)) / 2
        half = np.ptp(xs, axis=1) / 2
        ends = np.max(np.abs(xs), axis=1)
        assert (ends < radius).all()
        root = np.sqrt(radius**2 - mid**2)
        x = points[:, :, 3] - mid[:, None]
        height = root[:, None] - (mid / root)[:, None] * x - 0.5 * (radius**2 / root**3)[:, None] * x**2
        values += gain * (height - points[:, :, 4])
        # Taylor remainder for sqrt(R^2-x^2), using the largest |third derivative|
        # over the entire Bernstein x interval, including its end points.
        error = gain * 3 * radius**2 * ends / (radius**2 - ends**2) ** 2.5 * half**3 / 6
    controls = values @ QUARTIC_INVERSE.T
    return controls.max(1) + error if maximum else controls.min(1) - error


def projected_pairs(a, b):
    """Conservatively exclude hulls with disjoint 2D projections before bounding their depths."""
    keep = np.flatnonzero(
        np.all(
            np.maximum(a[:, :, :2].min(1) - b[:, :, :2].max(1), b[:, :, :2].min(1) - a[:, :, :2].max(1))
            <= ROUND_OFF,
            axis=1,
        )
    )
    for faces in (a, b):
        for i, j in EDGES:
            edge = faces[keep, j, :2] - faces[keep, i, :2]
            direction = (
                np.column_stack((-edge[:, 1], edge[:, 0])) / np.linalg.norm(edge, axis=1)[:, None]
            )
            ap = np.einsum("nkj,nj->nk", a[keep, :, :2], direction)
            bp = np.einsum("nkj,nj->nk", b[keep, :, :2], direction)
            keep = keep[(ap.max(1) + ROUND_OFF >= bp.min(1)) & (bp.max(1) + ROUND_OFF >= ap.min(1))]
    return keep


def enclosure(case, cell, *, cylinders=(None, None), width=WIDTH):
    depth, coords, residual = feasible_depth(case, cell, cylinders)
    lower = depth - ROUND_OFF
    # Match the target height, slope and curvature at the projected witness.
    # This changes only the tightness of the enclosure, since both faces use the same polynomial.
    uv = coords[2:]
    point = surface_at(cell, uv, cylinders[1])
    first = surface_gradient(cell, uv, cylinders[1])
    slope = np.linalg.solve(first[:, :2], first[:, 2])
    h = 1e-4
    second = np.stack(
        [
            (
                surface_gradient(cell, uv + h * e, cylinders[1])
                - surface_gradient(cell, uv - h * e, cylinders[1])
            )
            / (2 * h)
            for e in np.eye(2)
        ]
    )
    param_hessian = second[:, :, 2] - second[:, :, :2] @ slope
    inv = np.linalg.inv(first[:, :2])
    hessian = inv @ param_hessian @ inv.T
    linear = slope - hessian @ point[:2]
    poly = np.r_[0.0, linear, hessian[0, 0] / 2, hessian[0, 1], hessian[1, 1] / 2]
    a, b = case[None], cell[None]
    # Accumulate the upper bounds of all discarded depth branches. A projection exclusion
    # has no feasible point; its branch contributes nothing.
    upper = lower
    counts = []
    for level in range(21):
        keep = projected_pairs(a, b)
        a, b = a[keep], b[keep]
        if not len(a):
            break
        bounds = (
            residual_heights(b, poly, cylinders[1], maximum=True)
            - residual_heights(a, poly, cylinders[0], maximum=False)
            + ROUND_OFF
        )
        pending = bounds > lower + width
        upper = max(upper, float(bounds[~pending].max(initial=lower)))
        counts.append(int(pending.sum()))
        if not np.any(pending):
            break
        assert np.count_nonzero(pending) < 100_000 and level < 20, counts
        ac = CHILDREN @ a[pending, None]
        bc = CHILDREN @ b[pending, None]
        a = np.repeat(ac, 4, axis=1).reshape(-1, 6, a.shape[-1])
        b = np.tile(bc, (1, 4, 1, 1)).reshape(-1, 6, a.shape[-1])
    assert depth <= upper + ROUND_OFF and upper - lower <= width
    bary = [np.r_[uv, 1 - uv.sum()].tolist() for uv in (coords[:2], coords[2:])]
    return {
        "depth_nm_interval": [1e6 * lower, 1e6 * upper],
        "witness_depth_nm": 1e6 * depth,
        "case_barycentric": bary[0],
        "cell_barycentric": bary[1],
        "tangential_mismatch_mm": residual,
        "branches_above_tolerance": counts,
    }


def frame(target, inside):
    direction = normal(target, np.ones(3) / 3)
    direction[1] = 0.0
    direction /= np.linalg.norm(direction)
    direction *= np.sign(direction @ (target[:3].mean(0) - inside))
    # Reference cell axis is PCB Y. Orthonormalize against the fixed outward normal.
    y = np.array([0.0, 1.0, 0.0])
    x = np.cross(y, direction)
    x /= np.linalg.norm(x)
    return np.stack([x, np.cross(direction, x), direction], axis=1)


def load_poses(control=None):
    """Recover exactly the registered faces at each audited structural or startup station, in mm."""
    from basis_comparison import field_files
    from case_stress import source
    from dpf_readback import export
    from early_cell_clearance import outer_faces
    from film_identity import digest, verified
    from installed_cell_gap import target_connectivity
    from motion_surface import displacement_basis
    from snug_board_pull import BODIES, CAMPAIGN, positions, read
    from snug_pocket_dynamics import BASIS_PROOF, BRANCH, OUTPUT, STUDY
    from snug_unilateral_geometry import SURFACES, exact_faces

    old = read(SURFACES)
    original, neighbour = old["original_contact_element"], old["adjacent_pair"]["case_contact_element"]
    study = read(STUDY)
    verified(STUDY, old["startup_sha256"])
    static = old["static"] if control is None else control
    sta, _, rst = source(static["case"], CAMPAIGN)
    assert sta["rst_sha256"] == static["static_rst_sha256"]
    case_faces = exact_faces(rst, [original, neighbour])
    cell_skin = outer_faces(rst, [BODIES[1]])
    middle = set(map(tuple, np.sort(cell_skin, axis=1)))
    targets = {
        k: np.asarray(v)[[0, 1, 2, 4, 5, 7]]
        for k, v in target_connectivity(rst).items()
        if v[2] == v[3] and tuple(sorted(v[i] for i in (0, 1, 2, 4, 5, 7))) in middle
    }
    assert len(targets) == len(middle) == len({tuple(sorted(v)) for v in targets.values()})
    target_ids = np.array(list(targets))
    faces = np.vstack((case_faces, list(targets.values())))
    ids, ix = np.unique(faces, return_inverse=True)
    ix = ix.reshape(faces.shape)
    centre = rst.mesh.nodes[positions(rst.mesh.nnum, np.unique(cell_skin))].mean(0) * 1000
    static0 = rst.mesh.nodes[positions(rst.mesh.nnum, ids)]
    poses = {"initial": (1000 * static0)[ix]}
    fields = export(sta["case"], CAMPAIGN, list(range(1, rst.nsets + 1)))
    for k, row in enumerate(static["stations"], 1):
        if control is not None and k != rst.nsets:
            continue
        stem = fields / f"set_{k:04d}"
        index = stem.with_suffix(".ids")
        direction = stem.with_suffix(".u")
        verified(direction, row["displacements_sha256"])
        verified(index, row["ids_sha256"])
        nums = np.fromfile(index, "<i4")
        order = np.argsort(nums)
        u = np.fromfile(direction, "<f8").reshape(-1, 3)[order[positions(nums[order], ids)]]
        poses["static_" + str(k)] = (1000 * (static0 + u))[ix]
    identity = {
        "static_rst_sha256": sta["rst_sha256"],
        "case": sta["case"],
        "surface_checks_sha256": digest(SURFACES),
        "case_faces": [original, neighbour],
        "registered_target": old["adjacent_pair"]["cell_target_element"],
        "target_face_count": len(targets),
    }
    if control is not None:
        return poses, centre, target_ids, identity
    modal, _, rst = source(BRANCH + "_basis", CAMPAIGN)
    np.testing.assert_array_equal(faces, exact_faces(rst, [original, neighbour, *target_ids]))
    xyz = rst.mesh.nodes[positions(rst.mesh.nnum, ids)]
    locked = poses[f"static_{len(old['static']['stations'])}"]
    np.testing.assert_allclose(1000 * xyz[ix], locked, rtol=0, atol=1e-8)
    verified(BASIS_PROOF, study["basis_audit_sha256"])
    saved = read(BASIS_PROOF)
    assert saved["modal_rst_sha256"] == modal["rst_sha256"]
    modes = displacement_basis(
        rst, ids, field_files(modal["case"], CAMPAIGN, modal["rst_sha256"], rst.nsets)
    )
    path = OUTPUT / "reduction.npz"
    verified(path, saved["basis_sha256"])
    with np.load(path) as data:
        extra = data["fields"][positions(data["nodes"], ids)]
    for axis, ax in study["axes"].items():
        path = OUTPUT / f"{axis}_response.npz"
        verified(path, ax["history_sha256"])
        with np.load(path) as data:
            coords = 1000 * (
                xyz
                + np.tensordot(data["selected_q"], modes, axes=(1, 0))
                + np.einsum("nca,ta->tnc", extra, data["selected_residual"])
            )
            np.testing.assert_allclose(
                data["time_s"][data["selected"]],
                [r["time_s"] for r in old["axes"][axis]],
                rtol=0,
                atol=1e-14,
            )
        for row, x in zip(old["axes"][axis], coords, strict=True):
            poses[axis + "_" + row["station"]] = x[ix]
    identity.update(modal_rst_sha256=modal["rst_sha256"], startup_sha256=digest(STUDY))
    return poses, centre, target_ids, identity


@contextmanager
def registered_cad():
    import gmsh
    from case_fit import PCB_BOTTOM, PCB_CENTER, old
    from film_identity import verified
    from stage_snug_fit import STEP, STEP_HASH

    verified(STEP, STEP_HASH)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("registered_pockets")
        occ = gmsh.model.occ
        occ.importShapes(str(old))
        (cap,) = occ.importShapes(str(STEP))
        occ.rotate([cap], 0, 0, 0, 1, 0, 0, -np.pi / 2)
        occ.translate([cap], *PCB_CENTER, PCB_BOTTOM - 10 - 1.25)
        occ.synchronize()
        yield cap
    finally:
        gmsh.finalize()


def cad_cylinders(initial, origin, axes):
    """Read the two registered trimmed STEP cylinders and verify their equations in the depth frame."""
    import gmsh
    from case_fit import old
    from film_identity import digest
    from stage_snug_fit import STEP_HASH

    with registered_cad() as cap:
        gap = gmsh.model.occ.getDistance(*cap, 3, 19)[0]
        assert abs(gap - 0.002932) < 0.000001
        circles = []
        metadata = []
        for pts, body in zip(initial, (cap, (3, 19)), strict=True):
            centre = pts[:3].mean(0)
            candidates = []
            for dim, tag in gmsh.model.getBoundary([body], oriented=False):
                if gmsh.model.getType(dim, tag) != "Cylinder":
                    continue
                point, uv = gmsh.model.getClosestPoint(dim, tag, centre)
                if gmsh.model.isInside(dim, tag, uv, parametric=True):
                    candidates.append((np.linalg.norm(point - centre), tag))
            _, tag = min(candidates)
            lo, hi = gmsh.model.getParametrizationBounds(2, tag)

            def sample(count, axial_fraction, lo=lo, hi=hi, tag=tag):
                uv = np.column_stack(
                    (
                        np.linspace(lo[0], hi[0], count),
                        np.full(count, lo[1] + axial_fraction * (hi[1] - lo[1])),
                    )
                )
                return (
                    np.asarray(gmsh.model.getValue(2, tag, uv.ravel())).reshape(-1, 3) - origin
                ) @ axes

            fit = sample(31, 0.3)
            diff = sample(31, 0.7) - fit
            axis = diff[0] / np.linalg.norm(diff[0])
            np.testing.assert_allclose(diff, np.broadcast_to(diff[0], diff.shape), rtol=0, atol=1e-10)
            n = np.array([0.0, 0.0, 1.0])
            t = np.cross(axis, n)
            t /= np.linalg.norm(t)
            v = np.cross(t, axis)
            tv = np.column_stack((t, v))
            xz = fit @ tv
            A = np.column_stack((2 * xz, np.ones(len(xz))))
            solution = np.linalg.lstsq(A, (xz**2).sum(1), rcond=None)[0]
            c = solution[:2]
            r = np.sqrt(solution[2] + c @ c)
            check = sample(47, 0.78) @ tv
            mismatch = np.max(np.abs(np.linalg.norm(check - c, axis=1) - r))
            assert mismatch < 1e-10 and 10 < r < 12 and np.linalg.matrix_rank(A) == 3
            centers = ((pts - origin) @ axes) @ tv - c
            assert np.max(abs(np.linalg.norm(centers, axis=1) - r)) < 2e-6
            assert np.min(centers[:, 1]) > 0 and v[2] > 0.99
            circles.append({"shape": (r, 1 / v[2]), "transform": tv, "centre": c})
            metadata.append(
                {
                    "installed_gmsh_face": tag,
                    "centre_t_v_mm": c.tolist(),
                    "radius_mm": r,
                    "axial_direction_in_chart": axis.tolist(),
                    "cylinder_axes_in_chart": tv.tolist(),
                    "max_check_radius_error_mm": float(mismatch),
                }
            )
        return circles, {
            "cylinders": metadata,
            "native_step_sha256": STEP_HASH,
            "hardware_step_sha256": digest(old),
            "exact_unloaded_minimum_case_to_middle_cell_mm": gap,
        }


def manufactured_checks():
    """Known positive and negative extrema after FE interpolation or cylinder reconstruction."""
    xy = 0.4 * TRIANGLE[:, :2]
    x, y = xy.T
    cylinder = (10.0, 1.0)
    rest = np.sqrt(100 - x * x)
    roof = np.column_stack((x, y, rest))
    curvature = (x - 0.13) ** 2 + (y - 0.09) ** 2
    results = []
    for expected in (-12.0, 83.0):
        for corrected in (False, True):
            offset = curvature * 0.002 - expected * 1e-6
            side = roof.copy()
            side[:, 2] += offset
            if corrected:
                # Deliberately bias both initial and displaced interpolants on the case.
                side[:, 2] += 0.00025
                case = np.column_stack((side, x, rest + 0.00025))
                cell = np.column_stack((roof, x, rest))
                row = enclosure(bezier(case), bezier(cell), cylinders=(cylinder, cylinder))
            else:
                row = enclosure(bezier(side), bezier(roof))
            lo, hi = row["depth_nm_interval"]
            assert lo <= expected <= hi and hi - lo <= WIDTH * 1e6
            results.append(
                {"expected_nm": expected, "cad_restoration": corrected, "enclosure_nm": [lo, hi]}
            )
    return results


def check_cad_witnesses(points, face_ids):
    """Replay the deepest witnesses against their trimmed OpenCASCADE surfaces."""
    import gmsh

    with registered_cad():
        errors = []
        for point, tag in zip(points, face_ids, strict=True):
            on, uv = gmsh.model.getClosestPoint(2, tag, point)
            assert gmsh.model.isInside(2, tag, uv, parametric=True)
            errors.append(float(np.linalg.norm(point - on)))
        assert max(errors) < 1e-8, max(errors)
        return max(errors)


def analyse(poses, centre, ids, identity):
    rows = {}
    ref = 2 + np.flatnonzero(ids == identity["registered_target"]).item()
    initial = poses["initial"]
    origin = initial[ref, 0]
    axes = frame(bezier(initial[ref]), centre)
    q0 = bezier((initial - origin) @ axes)
    circles, meta = cad_cylinders(initial[[1, ref]], origin, axes)
    points = []
    face_ids = []
    # Test every middle-cell target projection. A branch excluded only in depth must
    # have an upper bound below a subsequently verified feasible point.
    for name, raw in poses.items():
        q = bezier((raw - origin) @ axes)
        rows[name] = {}
        for index, label in enumerate(("original", "second")):
            face = q[index]
            projection = projected_pairs(np.broadcast_to(face, (len(ids), 6, 3)), q[2:])
            depth_caps = q[2 + projection, :, 2].max(1) - face[:, 2].min()
            candidates = projection[depth_caps >= -0.1]
            skipped = depth_caps[depth_caps < -0.1]
            pairs = {}
            for j in candidates:
                patch = [index, j + 2]
                enriched = [
                    np.column_stack((q[m], q0[m] @ c["transform"] - c["centre"]))
                    for m, c in zip(patch, circles, strict=True)
                ]
                # All six interpolation nodes on each selected undeformed face belong to the
                # positive branch of the associated STEP cylinder.
                for m, c in zip(patch, circles, strict=True):
                    tv = ((initial[m] - origin) @ axes) @ c["transform"] - c["centre"]
                    assert (
                        tv[:, 1].min() > 0
                        and abs(np.linalg.norm(tv, axis=1) - c["shape"][0]).max() < 2e-6
                    )
                fe = enclosure(face, q[j + 2])
                cad = enclosure(*enriched, cylinders=[c["shape"] for c in circles])
                for key, entry in [("FE", fe), ("CAD_at_same_displacements", cad)]:
                    witness_points = []
                    for m, c, bary in zip(
                        patch,
                        circles,
                        (entry["case_barycentric"], entry["cell_barycentric"]),
                        strict=True,
                    ):
                        weights = basis(np.array(bary))
                        point = weights @ q0[m]
                        posed_point = weights @ q[m]
                        if key.startswith("CAD"):
                            t, v = point @ c["transform"] - c["centre"]
                            radius, gain = c["shape"]
                            shift = gain * (np.sqrt(radius**2 - t * t) - v)
                            point[2] += shift
                            posed_point[2] += shift
                            points.append(origin + point @ axes.T)
                        witness_points.append(posed_point)
                    delta = witness_points[1] - witness_points[0]
                    np.testing.assert_allclose(
                        delta, [0.0, 0.0, entry["witness_depth_nm"] * 1e-6], rtol=0, atol=1e-11
                    )
                    # Preserve material location on the original case for plotting and registration.
                    entry["case_reference_xyz_mm"] = (
                        origin + (basis(entry["case_barycentric"]) @ q0[index]) @ axes.T
                    ).tolist()
                    if key.startswith("CAD"):
                        face_ids.extend(cadface["installed_gmsh_face"] for cadface in meta["cylinders"])
                pairs[int(ids[j])] = {"FE": fe, "CAD_at_same_displacements": cad}
            assert pairs
            envelope = {
                key: np.max([v[key]["depth_nm_interval"] for v in pairs.values()], axis=0).tolist()
                for key in ("FE", "CAD_at_same_displacements")
            }
            assert skipped.max(initial=-np.inf) * 1e6 < envelope["FE"][0] - 1.0
            rows[name][label] = {
                "targets": pairs,
                "depth_nm_interval": envelope,
                "targets_with_overlapping_projected_hulls": len(projection),
            }
    err = check_cad_witnesses(points, face_ids)
    return dict(
        **identity,
        chart_origin_mm=origin.tolist(),
        chart_axes=axes.tolist(),
        registered_CAD=meta,
        maximum_trimmed_STEP_witness_residual_mm=err,
        interval_tolerance_nm=WIDTH * 1e6,
        stations=rows,
        manufactured_checks=manufactured_checks(),
        scope="Extremal signed overlaps along the fixed outward radial direction on two selected PLA faces. "
        "Positive is geometric overlap; negative is directional clearance. FE uses the native quadratic "
        "geometry. The CAD sensitivity restores only the two local reference cylinders along that direction "
        "with archived nodal displacements and their FE interpolation held fixed. Forces require native equilibrium.",
    )


if __name__ == "__main__":
    from film_identity import write_json
    from snug_board_pull import AUDIT

    result = analyse(*load_poses())
    write_json(AUDIT / "aluminium_curved_pocket_depth.json", result)
    for key in ("static_8", *(f"{a}_peak_spring_opening" for a in "XYZ")):
        print(key, {k: v["depth_nm_interval"] for k, v in result["stations"][key].items()}, flush=True)

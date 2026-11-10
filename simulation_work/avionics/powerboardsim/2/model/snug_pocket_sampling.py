"""Check the radial clearance at every middle-pocket Gauss point on the registered cell surface."""

import argparse
from typing import NamedTuple

import numpy as np
from case_stress import source
from early_cell_clearance import bezier
from extend_board import NODE
from film_identity import digest, verified, write_json
from installed_cell_gap import target_connectivity
from seeded_motion import FS
from snug_board_pull import AUDIT, CAMPAIGN, positions, read
from snug_contact_startup import exact_check
from snug_contact_vibration import BRANCHES, CACHE, coordinates
from snug_locked_contact import surface_owners
from snug_pocket_depth import MAP, QUARTIC_INVERSE
from snug_pocket_faces import SHAPE
from snug_unilateral_geometry import exact_faces
from stage_snug_fit import MESH, STEP, STEP_HASH, input_record


def shape(uv):
    u, v = uv.T
    w = 1 - u - v
    vals = np.column_stack(
        (u * (2 * u - 1), v * (2 * v - 1), w * (2 * w - 1), 4 * u * v, 4 * v * w, 4 * w * u)
    )
    du = np.column_stack((4 * u - 1, 0 * u, 1 - 4 * w, 4 * v, -4 * v, 4 * (w - u)))
    dv = np.column_stack((0 * v, 4 * v - 1, 1 - 4 * w, 4 * u, 4 * (w - v), -4 * u))
    return vals, du, dv


class CylinderAxis(NamedTuple):
    centre: np.ndarray
    direction: np.ndarray

    @property
    def xz(self):
        return self.centre[[0, 2]]

    def transverse(self, v):
        return v - np.einsum("...j,j->...", v, self.direction)[..., None] * self.direction


def cylinder_correction(x, axis, radius):
    radial = axis.transverse(x - axis.centre)
    length = np.linalg.norm(radial, axis=1)
    n = radial / length[:, None]
    return (radius - length)[:, None] * n, n, radius / length


def ray_root(p, face, undeformed, centre, radius, restore):
    """Intersect radial rays with quadratic cell patches, optionally restoring the original STEP curvature."""
    radial = p[:, [0, 2]] - centre.xz
    n = radial / np.linalg.norm(radial, axis=1)[:, None]
    tangent = np.column_stack((-n[:, 1], n[:, 0]))
    uv = np.full((len(p), 2), 1 / 3)
    dot = lambda x, y: np.einsum("ij,ij->i", x, y)
    for _ in range(8):
        s, du, dv = shape(uv)
        val, dx, dy = [np.einsum("ij,ijk->ik", mat, face) for mat in (s, du, dv)]
        if restore:
            initial, ds, dt = [np.einsum("ij,ijk->ik", mat, undeformed) for mat in (s, du, dv)]
            delta, normal, scale = cylinder_correction(initial, centre, radius)
            val += delta
            for vector, base in ((dx, ds), (dy, dt)):
                x = centre.transverse(base)
                vector += (scale - 1)[:, None] * x - (scale * dot(normal, x))[:, None] * normal
        r = val - p
        err1 = r[:, 1]
        err2 = dot(r[:, [0, 2]], tangent)
        if max(abs(err1).max(), abs(err2).max()) < 2e-10:
            break
        a = dx[:, 1]
        b = dy[:, 1]
        c = dot(dx[:, [0, 2]], tangent)
        d = dot(dy[:, [0, 2]], tangent)
        det = a * d - b * c
        assert abs(det).min() > 1e-9, abs(det).min()
        uv[:, 0] -= (d * err1 - b * err2) / det
        uv[:, 1] -= (a * err2 - c * err1) / det
    else:
        raise ArithmeticError("Radial face projection failed to converge")
    valid = (uv.min(axis=1) >= -1e-9) & (uv.sum(axis=1) <= 1 + 1e-9)
    return dot((p - val)[:, [0, 2]], n), valid, uv


def project(p, face, undeformed, centre, radius, restore):
    """Exclude projected convex hulls before solving on the small set of admissible targets."""
    radial = p[:, [0, 2]] - centre.xz
    n = radial / np.linalg.norm(radial, axis=1)[:, None]
    tangent = np.column_stack((-n[:, 1], n[:, 0]))
    ctrl = bezier(face) - p[:, None, :]
    chart = np.stack((ctrl[:, :, 1], np.einsum("nij,nj->ni", ctrl[:, :, [0, 2]], tangent)), axis=2)
    margin = 0.100001 if restore else 1e-9
    valid = np.all((chart.min(1) <= margin) & (chart.max(1) >= -margin), axis=1)
    for i, j in ((0, 1), (1, 2), (2, 0)):
        edge = chart[:, j] - chart[:, i]
        norm = np.linalg.norm(edge, axis=1)
        direction = np.column_stack((-edge[:, 1], edge[:, 0])) / np.maximum(norm[:, None], 1e-28)
        bound = np.einsum("nij,nj->ni", chart, direction)
        valid &= (bound.min(1) <= margin) & (bound.max(1) >= -margin)
    ix = np.flatnonzero(valid)
    gap = np.full(len(p), np.inf)
    uv = np.zeros((len(p), 2))
    if len(ix):
        gap[ix], valid[ix], uv[ix] = ray_root(p[ix], face[ix], undeformed[ix], centre, radius, restore)
    return gap, valid, uv


def groups(branch, data):
    ref = input_record(branch + "_static")
    sp, _, sr = source(branch + "_static", CAMPAIGN)
    return cylindrical_surfaces(ref, sr, data["nodes"], data["nodes"][data["middle"]]), sp


def cylindrical_surfaces(ref, sr, nodes, middle_faces):
    """Map the registered pocket and cell barrel triangles to a supplied sorted node array."""
    mesh = MESH / f"case_{ref['size_mm']}.npz"
    owners = surface_owners(sr, mesh, ref.get("case_node_start", NODE))
    caps = np.array(sorted(e for e, tag in owners.items() if tag == 17))
    skin = set(map(tuple, np.sort(middle_faces, axis=1)))
    targets = np.array(
        sorted(
            e
            for e, v in target_connectivity(sr).items()
            if v[2] == v[3] and tuple(sorted(v[i] for i in (0, 1, 2, 4, 5, 7))) in skin
        )
    )
    assert len(targets) == len(skin)
    cads = read(AUDIT / "aluminium_curved_pocket_depth.json")
    assert cads["registered_CAD"]["native_step_sha256"] == STEP_HASH == ref["step_sha256"]
    verified(STEP, STEP_HASH)
    origin = np.array(cads["chart_origin_mm"])
    axes = np.array(cads["chart_axes"])
    out = []
    for elem, c in zip((caps, targets), cads["registered_CAD"]["cylinders"], strict=True):
        ctr = origin + (np.array(c["cylinder_axes_in_chart"]) @ c["centre_t_v_mm"]) @ axes.T
        ctr = CylinderAxis(ctr, axes @ np.array(c["axial_direction_in_chart"]))
        rad = c["radius_mm"]
        f = exact_faces(sr, elem)
        undeformed = 1000 * sr.mesh.nodes[positions(sr.mesh.nnum, f)]
        dev = abs(np.linalg.norm(ctr.transverse(undeformed - ctr.centre), axis=2) - rad).max(1)
        select = dev < 2e-6
        if out:
            assert select.any() and not select.all()
        else:
            assert select.all()
        out.append((elem[select], positions(nodes, f[select]), undeformed[select], ctr, rad))
    return out


def candidates(case_start, case_delta, cell_start, cell_delta, centre, radius, cell_initial):
    # Control-point convex hulls enclose every instantaneous target facet. Undeformed
    # STEP radial restoration is bounded by the maximum quadratic radial deviation.
    target = bezier(cell_start)
    init = bezier(cell_initial)

    def radius_bounds(ctrl):
        xy = centre.transverse(ctrl - centre.centre)
        surface = np.einsum("qn,fnj->fqj", MAP, xy)
        coeff = ((surface**2).sum(axis=2) - radius**2) @ QUARTIC_INVERSE.T
        return np.sqrt(radius**2 + coeff.min(1)), np.sqrt(radius**2 + coeff.max(1))

    rlo, rhi = radius_bounds(init)
    cad_bound = np.maximum(abs(rhi - radius), abs(rlo - radius))
    assert cad_bound.max() < 0.1, cad_bound.max()
    # Radial restoration uses each original cylinder axis, including the measured cell tilt. Keep
    # this displacement in the conservative target envelope for both surface variants.
    delta = cell_delta + cad_bound[:, None]
    low_y = target[:, :, 1].min(1) - delta.max(1)
    high_y = target[:, :, 1].max(1) + delta.max(1)
    tgt = target[:, :, [0, 2]] - centre.xz
    length = np.linalg.norm(tgt, axis=2)
    angle = np.arctan2(tgt[:, :, 1], tgt[:, :, 0])
    angle_c = angle[:, 0]
    assert np.max(delta / length) < 0.9
    spread = np.max(
        abs(np.angle(np.exp(1j * (angle - angle_c[:, None])))) + np.arcsin(delta / length), axis=1
    )
    assert spread.max() < np.pi / 2
    # The radius bound below uses the exact reference cylinder plus the maximum
    # total change (including installed deformation and interpolation error).
    assert (
        np.linalg.norm(centre.direction[[0, 2]]) * np.max(np.linalg.norm(target - centre.centre, axis=2))
        < 1e-5
    )
    radial_limit = np.max(radius_bounds(target)[1] + delta.max(1)) + 1e-5
    r = case_start[:, [0, 2]] - centre.xz
    rr = np.linalg.norm(r, axis=1)
    assert np.max(case_delta / rr) < 0.9
    theta = np.arctan2(r[:, 1], r[:, 0])
    sweep = np.arcsin(case_delta / rr)
    gi = []
    fi = []
    for i in np.flatnonzero((rr - case_delta) <= radial_limit + 0.05):
        da = abs(np.angle(np.exp(1j * (theta[i] - angle_c))))
        near = np.flatnonzero(
            (da <= spread + sweep[i] + 1e-8)
            & (case_start[i, 1] + case_delta[i] >= low_y - 1e-7)
            & (case_start[i, 1] - case_delta[i] <= high_y + 1e-7)
        )
        gi.extend([i] * len(near))
        fi.extend(near)
    return np.array(gi), np.array(fi)


def scan(
    axis,
    area,
    branch,
    samples,
    hist,
    ca,
    ct,
    faces,
    tgt,
    case0,
    cell0,
    starts,
    shapes,
    shift,
    lock,
    field,
    tc,
    rt,
    active,
):
    max_q = abs(hist).max(0)
    case_limit = np.linalg.norm(abs(shapes) @ max_q, axis=1) + np.linalg.norm(shift, axis=1) + 1e-8
    cell_bezier = bezier(field[tgt].transpose(0, 3, 1, 2)).transpose(0, 2, 3, 1)
    cell_limit = np.linalg.norm(abs(cell_bezier) @ max_q, axis=2) + 1e-8
    gi, fi = candidates(starts, case_limit, lock[tgt], cell_limit, tc, rt, cell0)
    station = int(np.flatnonzero(samples == area["axes"][axis]["station"]).item())
    witness = area["axes"]["Y"]["models"][branch]["common_time_global_surfaces"]["middle"][
        "witness_elements"
    ]["case_contact_element"]
    case_ids = np.repeat(ca, 3)
    use, source_index = np.unique(gi, return_inverse=True)
    selected, target_index = np.unique(fi, return_inverse=True)
    source_index = source_index.ravel()
    target_index = target_index.ravel()
    assert np.isin(active, use).all()
    dim = len(samples)
    minima = np.full((dim, 2, 3), np.inf)
    chosen = np.full((dim, 2, 3, 2), -1, dtype=int)
    counts = np.zeros((dim, 2, 3), int)
    labels = ("all", "initially_unloaded", "witness_triangle")
    masks = (np.ones(len(gi), bool), ~np.isin(gi, active), case_ids[gi] == witness)
    lock_rows = []
    matched_rows = []
    initial_sources = starts[use]
    input_shapes = shapes[use]
    initial_targets = lock[tgt[selected]]
    target_shapes = field[tgt[selected]]
    batch = max(1, 40000 // len(gi))
    for start in range(0, dim, batch):
        end = min(start + batch, dim)
        coeff = hist[start:end]
        pp = initial_sources + (coeff @ input_shapes.reshape(-1, hist.shape[1]).T).reshape(
            -1, *initial_sources.shape
        )
        bb = initial_targets + (coeff @ target_shapes.reshape(-1, hist.shape[1]).T).reshape(
            -1, *initial_targets.shape
        )
        ntime = end - start
        for form in (0, 1):
            queries = pp[:, source_index] + form * shift[gi]
            v, valid, bary = project(
                queries.reshape(-1, 3),
                bb[:, target_index].reshape(-1, 6, 3),
                np.broadcast_to(cell0[fi], (ntime, len(fi), 6, 3)).reshape(-1, 6, 3),
                tc,
                rt,
                bool(form),
            )
            v = v.reshape(ntime, len(gi))
            valid = valid.reshape(v.shape)
            # A station may lie on a shared target edge. Count each physical case point once.
            value = np.where(valid, v, np.inf)
            for k, mask in enumerate(masks):
                rows = np.flatnonzero(mask)
                if not len(rows):
                    continue
                sub = value[:, rows]
                loc = rows[np.argmin(sub, axis=1)]
                minima[start:end, form, k] = value[np.arange(ntime), loc]
                chosen[start:end, form, k] = np.column_stack((gi[loc], ct[fi[loc]]))
                seen = np.zeros((ntime, len(use)), bool)
                ti, pairs = np.nonzero(sub < -1e-9)
                seen[ti, source_index[rows[pairs]]] = True
                counts[start:end, form, k] = seen.sum(1)
            for index, record in ((0, lock_rows), (station, matched_rows)):
                if start <= index < end:
                    j = index - start
                    pairrows = np.flatnonzero(
                        valid[j] & ((value[j] < 0) | np.isin(gi, active) | (case_ids[gi] == witness))
                    )
                    record.extend(
                        {
                            "surface": ("mesh", "STEP")[form],
                            "element": int(case_ids[gi[h]]),
                            "gp": int(1 + gi[h] % 3),
                            "target": int(ct[fi[h]]),
                            "gap_um": float(1000 * v[j, h]),
                            "uv": bary.reshape(ntime, -1, 2)[j, h].tolist(),
                            "active_at_lock": bool(gi[h] in active),
                        }
                        for h in pairrows
                    )
    assert np.isfinite(minima[:, :, :2]).all() and minima[:, :, :2].max() < 0.05
    events = {}
    for form, kind in enumerate(("mesh", "STEP")):
        by = {}
        for k, label in enumerate(labels):
            v = minima[:, form, k]
            if not np.isfinite(v).any():
                by[label] = {"cylindrical_projection": False}
                continue
            passed = np.flatnonzero(v < -1e-9)
            idx = int(v.argmin())
            point, target = chosen[idx, form, k]
            by[label] = {
                "minimum_gap_um": float(1000 * v[idx]),
                "minimum_time_ms": 1000 * samples[idx] / FS,
                "element": int(case_ids[point]),
                "gp": int(point % 3 + 1),
                "target": int(target),
                "first_negative_sample": int(samples[passed[0]]) if len(passed) else None,
                "maximum_negative_points": int(counts[:, form, k].max()),
                "matched_minimum_gap_um": float(1000 * v[station]),
                "lock_minimum_gap_um": float(1000 * v[0]),
                "matched_negative_points": int(counts[station, form, k]),
            }
        events[kind] = by
    info = {
        "candidate_pairs": len(gi),
        "candidate_gauss_stations": len(use),
        "matched_sample": int(samples[station]),
        "matched_time_ms": 1000 * samples[station] / FS,
        "matched_witness_element": int(witness),
        "lock": lock_rows,
        "matched": matched_rows,
        "events": events,
    }
    return minima, chosen, info


def run(branch):
    bp = AUDIT / f"{branch}_contact_vibration_basis.json"
    br = read(bp)
    study = AUDIT / f"{branch}_contact_vibration.json"
    run = read(study)
    assert run["basis_proof_sha256"] == digest(bp)
    directory = CACHE / (branch + "_basis") / f"coupled_contact_b{br['residual_blocks']}"
    verified(directory / "basis.npz", br["basis_sha256"])
    with np.load(directory / "basis.npz") as cf:
        data = {k: cf[k] for k in cf.files}
    (case, cell), static = groups(branch, data)
    ca, faces, case0, cc, rc = case
    ct, tgt, cell0, tc, rt = cell
    lock = data["positions"] * 1000
    field = data["skin"] * 1000
    # Order is native contact element then its three integration points.
    gauss0 = np.einsum("ng,fnk->fgk", SHAPE, case0).reshape(-1, 3)
    starts = np.einsum("ng,fnk->fgk", SHAPE, lock[faces]).reshape(-1, 3)
    shapes = np.einsum("ng,fnkm->fgkm", SHAPE, field[faces]).reshape(len(starts), 3, -1)
    delta_src, _, _ = cylinder_correction(gauss0, cc, rc)
    shift = delta_src
    active_record = read(AUDIT / f"{branch}_pocket_face_unloading.json")
    active = {(p["element"], p["point"]) for p in active_record["integration_points"]}
    order = {(int(el), i + 1): 3 * j + i for j, el in enumerate(ca) for i in range(3)}
    ids = np.array(sorted(order[key] for key in active))
    area = read(AUDIT / "matched_contact_startup.json")
    result = {}
    for ax, axis in enumerate("XYZ"):
        h = directory / (axis + "_history.npz")
        verified(h, run["axes"][axis]["history_sha256"])
        with np.load(h) as t:
            acc = t["load"]
        om, B, drive, T = coordinates(data, br["residual_blocks"])
        q, _ = exact_check(om, B, data["k"], data["g"], drive[:, ax], acc, 4)
        samples = np.unique(np.r_[np.arange(0, 2049, 16), area["axes"][axis]["station"]])
        q = q[::4]
        n = br["native_modes"]
        full = np.column_stack((q[:, :n], q[:, n:] @ T.T))
        hist = full[samples]
        output = directory / (axis + "_pocket_sampling.npz")
        values, picks, metadata = scan(
            axis,
            area,
            branch,
            samples,
            hist,
            ca,
            ct,
            faces,
            tgt,
            case0,
            cell0,
            starts,
            shapes,
            shift,
            lock,
            field,
            tc,
            rt,
            ids,
        )
        early = metadata["events"]["mesh"]["initially_unloaded"]["first_negative_sample"]
        if early is not None:
            samples = np.unique(np.r_[np.arange(early + 1), samples])
            values, picks, metadata = scan(
                axis,
                area,
                branch,
                samples,
                full[samples],
                ca,
                ct,
                faces,
                tgt,
                case0,
                cell0,
                starts,
                shapes,
                shift,
                lock,
                field,
                tc,
                rt,
                ids,
            )
        np.savez(
            output,
            samples=samples,
            minimum_gap_mm=values,
            closest_point_and_target=picks,
            case_elements=ca,
            target_elements=ct,
            active_ids=ids,
        )
        result[axis] = dict(
            **metadata, history_sha256=digest(output), input_sha256=run["axes"][axis]["input_sha256"]
        )
        print(
            branch,
            axis,
            metadata["candidate_pairs"],
            metadata["events"]["mesh"]["initially_unloaded"],
            flush=True,
        )
    write_json(
        AUDIT / f"{branch}_pocket_sampling.json",
        {
            "branch": branch,
            "static_rst_sha256": static["rst_sha256"],
            "basis_audit_sha256": digest(bp),
            "dynamic_audit_sha256": digest(study),
            "matched_station_sha256": digest(AUDIT / "matched_contact_startup.json"),
            "integration_points": len(starts),
            "middle_case_triangles": len(ca),
            "cylindrical_cell_triangles": len(ct),
            "axes": result,
            "scope": "Signed radial ray gap at the three Gauss stations of every middle cylindrical pocket contact triangle, at every original input station through the first new FE intrusion, then every sixteenth input sample and the matched comparison sample. STEP reconstruction restores the undeformed cylinder radius before adding the same nodal displacement. This is a geometric contact-detection check on prescribed poses.",
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("branch", choices=BRANCHES)
    run(p.parse_args().branch)

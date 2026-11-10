"""Test new middle-pocket contacts as the amplitude of each nine-second vibration record increases."""

import argparse

import numpy as np
from audit_motion import native_series
from early_cell_clearance import bezier, subdivision_weights
from film_cell_contact import TOL_MM, candidate_pairs
from film_cell_timestep import linear_input_displacement
from film_identity import digest, verified, write_json
from scipy.optimize import brentq
from seeded_motion import FS, excitation
from snug_board_pull import AUDIT, CAMPAIGN, ROOT, read
from snug_contact_vibration import BRANCHES, CACHE, coordinates
from snug_pocket_faces import SHAPE
from snug_pocket_sampling import candidates, groups, project, ray_root, shape
from snug_vibration_level import exact_response


def lock_geometry(branch, data, known):
    (case, cell), locked = groups(branch, data)
    ids, faces, _, _, _ = case
    xyz = data["positions"] * 1000
    modes = data["skin"][:, :, : len(data["frequency"])] * 1000
    active = {tuple(map(int, s.split("."))) for s in data["labels"][:-4]}
    assert active == set(map(tuple, known["original_bearing_points"]))
    assert locked["rst_sha256"] == known["parent_rst_sha256"]
    element = np.repeat(ids, 3)
    point = np.tile([1, 2, 3], len(ids))
    clear = [i for i, key in enumerate(zip(element, point, strict=True)) if key not in active]
    assert len(clear) == known["initially_unloaded_points"]
    p = np.einsum("ng,fnk->fgk", SHAPE, xyz[faces]).reshape(-1, 3)[clear]
    pm = np.einsum("ng,fnkm->fgkm", SHAPE, modes[faces]).reshape(len(element), 3, -1)[clear]
    target_ids, sites, original, axis, radius = cell
    f = xyz[sites]
    fm = modes[sites]
    i, j = candidates(p, np.zeros(len(p)), f, np.zeros(f.shape[:2]), axis, radius, original)
    gap, inside, uv = project(p[i], f[j], original[j], axis, radius, False)
    i, j, uv, gap = i[inside], j[inside], uv[inside], gap[inside]
    assert (gap > 0).all()
    return {
        "p": p,
        "pm": pm,
        "f": f,
        "fm": fm,
        "original": original,
        "axis": axis,
        "radius": radius,
        "i": i,
        "j": j,
        "uv": uv,
        "gap": gap,
        "target_ids": target_ids,
        "element": element[clear],
        "point": point[clear],
        "full_cell": xyz[data["middle"]],
        "full_modes": modes[data["middle"]],
        "case_faces": faces,
        "target_sites": sites,
        "case_ids": ids,
    }


def crossing(point, point_delta, face, face_delta, rest, axis, radius, upper):
    def sample(scale):
        pos = (point + scale * point_delta)[None]
        patch = (face + scale * face_delta)[None]
        gap, inside, uv = ray_root(pos, patch, rest, axis, radius, False)
        return gap.item(), inside.item(), uv[0]

    hi, valid, _ = sample(upper)
    if not valid or hi > 0:
        return None
    assert sample(0)[0] > 0
    scale = brentq(lambda a: sample(a)[0], 0, upper, xtol=1e-14)
    gap, valid, uv = sample(scale)
    assert valid and abs(gap) < 1e-9
    assert sample(0.999 * scale)[0] > 0 and sample(1.001 * scale)[0] < 0
    target = shape(uv[None])[0][0] @ (face + scale * face_delta)
    error = np.linalg.norm(target - (point + scale * point_delta))
    assert error < 1e-9
    return scale, uv, error


def witness(g, q, rms, ceiling):
    """Rank projected open sites by first-order gap change, then solve on both deformed quadratic surfaces."""
    i, j, uv, gap = (g[k] for k in ("i", "j", "uv", "gap"))
    w, du, dv = shape(uv)
    normal = np.cross(np.einsum("ij,ijk->ik", du, g["f"][j]), np.einsum("ij,ijk->ik", dv, g["f"][j]))
    relative = g["pm"][i] - np.einsum("ij,ijkm->ikm", w, g["fm"][j])
    tangent_gap = np.einsum("ij,ijm->im", normal, relative)
    radial = g["p"][i][:, [0, 2]] - g["axis"].xz
    radial /= np.linalg.norm(radial, axis=1)[:, None]
    denominator = np.einsum("ij,ij->i", normal[:, [0, 2]], radial)
    derivative = tangent_gap / denominator[:, None]
    assert np.isfinite(derivative).all()
    # These bounds screen candidates for a witness only. Spatial certification is independent.
    max_q = np.max(abs(q), axis=0)
    keep = np.flatnonzero(gap < 2 * ceiling * (abs(derivative) @ max_q))
    best = None
    for start in range(0, len(keep), 8):
        rows = keep[start : start + 8]
        adverse = -(q @ derivative[rows].T)
        station = adverse.argmax(axis=0)
        for row, step, peak in zip(rows, station, adverse[station, np.arange(len(rows))], strict=True):
            if peak <= 0 or gap[row] / peak > 1.5 * ceiling:
                continue
            a, b = i[row], j[row]
            dp = g["pm"][a] @ q[step]
            df = g["fm"][b] @ q[step]

            bracket = crossing(
                g["p"][a],
                dp,
                g["f"][b],
                df,
                g["original"][b : b + 1],
                g["axis"],
                g["radius"],
                min(ceiling, 1.5 * gap[row] / peak),
            )
            if bracket is None:
                continue
            root, where, error = bracket
            if best is None or root < best["scale"]:
                best = {
                    "scale": float(root),
                    "stationary_rms_g": float(root * rms),
                    "sample": int(step),
                    "time_s": float(step / FS),
                    "element": int(g["element"][a]),
                    "point": int(g["point"][a]),
                    "target": int(g["target_ids"][b]),
                    "locked_radial_gap_nm": float(1e6 * gap[row]),
                    "target_uv": where.tolist(),
                    "coincidence_error_mm": float(error),
                }
    return best


def certify(g, q, amplitude):
    """Exclude coincidence on every closed-cell facet at all sampled times and intervening input scales."""
    mesh = bezier(g["full_cell"])
    modes = bezier(g["full_modes"].transpose(0, 3, 1, 2)).transpose(0, 2, 3, 1)
    max_q = np.max(abs(q), axis=0) * amplitude
    pd = abs(g["pm"]) @ max_q + TOL_MM
    fd = abs(modes) @ max_q + TOL_MM
    i, j = candidate_pairs((g["p"] - pd, g["p"] + pd), ((mesh - fd).min(1), (mesh + fd).max(1)))
    sizes = []
    tested = 0
    for start in range(0, len(i), 1500):
        point, target = i[start : start + 1500], j[start : start + 1500]
        ctrl = mesh[target] - g["p"][point, None]
        field = modes[target] - g["pm"][point, None]
        counts, evaluated = exclude_patches(q, amplitude, max_q, ctrl, field)
        if len(counts) > len(sizes):
            sizes += [0] * (len(counts) - len(sizes))
        for depth, value in enumerate(counts):
            sizes[depth] += value
        tested += evaluated
    assert len(i) and sizes[-1] == 0
    return {
        "scale": amplitude,
        "broad_phase_pairs": len(i),
        "unresolved_per_depth": sizes,
        "faces_checked_with_full_time_series": tested,
    }


def exclude_patches(q, amplitude, max_q, ctrl, field):
    weights = subdivision_weights()
    sizes = []
    tested = 0
    for depth in range(16):
        # Each patch is a convex combination of six moving Bernstein controls. Subtract
        # the same Gauss point from all six before bounding common modal translations.
        span = abs(field) @ max_q
        lo, hi = (ctrl - span).min(1), (ctrl + span).max(1)
        keep = np.flatnonzero(np.all((lo <= TOL_MM) & (hi >= -TOL_MM), axis=1))
        ctrl, field = ctrl[keep], field[keep]
        plane = np.cross(ctrl[:, 1] - ctrl[:, 0], ctrl[:, 2] - ctrl[:, 0])
        length = np.linalg.norm(plane, axis=1)
        assert np.isfinite(length).all() and (length > 0).all()
        plane /= length[:, None]
        base = np.einsum("nfc,nc->nf", ctrl, plane)
        direction = np.einsum("nfcm,nc->nfm", field, plane)
        spread = abs(direction) @ max_q
        keep = np.flatnonzero(((base - spread).min(1) <= TOL_MM) & ((base + spread).max(1) >= -TOL_MM))
        if depth >= 7 and len(keep):
            # Evaluate the correlated vibration on each remaining face normal. Zero
            # amplitude and the selected amplitude enclose every intermediate amplitude.
            retained = []
            for start in range(0, len(keep), 8):
                chunk = keep[start : start + 8]
                directions = direction[chunk].reshape(-1, q.shape[1])
                lower, upper = base[chunk].copy(), base[chunk].copy()
                for first in range(0, len(q), 32768):
                    delta = amplitude * (q[first : first + 32768] @ directions.T)
                    lower = np.minimum(lower, base[chunk] + delta.min(0).reshape(lower.shape))
                    upper = np.maximum(upper, base[chunk] + delta.max(0).reshape(upper.shape))
                retained.extend(chunk[(lower.min(1) <= TOL_MM) & (upper.max(1) >= -TOL_MM)])
                tested += len(chunk)
            keep = np.asarray(retained, dtype=int)
        sizes.append(len(keep))
        if not len(keep):
            return sizes, tested
        ctrl = (weights @ ctrl[keep, None]).reshape(-1, 6, 3)
        field = (weights @ field[keep].reshape(len(keep), 1, 6, -1)).reshape(-1, 6, 3, q.shape[1])
    raise ValueError(f"Could not certify all point-to-cell distances at {amplitude}: {sizes}")


def repeat_crossing(g, data, hit, axis, ref, blocks):
    """Repeat the attained crossing with an independently integrated waveform and a larger modal basis."""
    face_index = int(np.flatnonzero(g["case_ids"] == hit["element"]).item())
    cell_index = int(np.flatnonzero(g["target_ids"] == hit["target"]).item())
    case_weights = SHAPE[:, hit["point"] - 1]
    case_u = case_weights @ (1000 * data["skin"][g["case_faces"][face_index]]).reshape(6, -1)
    case_u = case_u.reshape(3, -1)
    # Use relative coordinates for coincidence. The relative control has the same root under
    # arbitrary time-dependent rigid translation of the entire case and cell.
    rel = 1000 * data["skin"][g["target_sites"][cell_index]] - case_u[None]
    ix = np.flatnonzero((g["element"] == hit["element"]) & (g["point"] == hit["point"])).item()
    p = g["p"][ix]
    face = g["f"][cell_index]
    rest = g["original"][cell_index : cell_index + 1]
    _, ok, uv = project(p[None], face[None], rest, g["axis"], g["radius"], False)
    assert ok.item()
    w, du, dv = shape(uv)
    nvec = np.cross(du @ face, dv @ face)[0]
    if nvec @ (p - (w @ face)[0]) < 0:
        nvec = -nvec
    normal_shape = np.einsum("i,icm,c->m", w[0], rel, nvec)[:, None]
    input_path = ROOT / ".runtime/motion_loads" / (axis + ".txt")
    verified(input_path, ref["input_sha256"])
    _, load = np.loadtxt(input_path, skiprows=1).T
    n = len(data["frequency"])
    result = []
    for extra, subdivision, cutoff in (
        (0, 1, 3500),
        (0, 1, 4000),
        (blocks, 1, 4000),
        (blocks, 2, 4000),
    ):
        omega, _, drive, rot = coordinates(data, extra)
        hz = omega / (2 * np.pi)
        use = (np.arange(len(hz)) >= n) | (hz <= cutoff)
        vec = np.vstack((normal_shape[:n], rot.T @ normal_shape[n : len(hz)]))
        rate = FS * subdivision
        samples = subdivision * (len(load) - 1) + 1
        signal = (
            load
            if subdivision == 1
            else np.interp(np.arange(samples) / subdivision, np.arange(len(load)), load)
        )
        fac = drive[:, "XYZ".index(axis)]
        trace = exact_response(hz[use], fac[use], vec[use], signal, rate)[:, 0]
        station = int(trace.argmax())
        hist = np.array(
            [
                linear_input_displacement(f, v, signal[: station + 1], 1 / rate)[-1]
                for f, v in zip(hz[use], fac[use], strict=True)
            ]
        )
        q = np.zeros(len(hz))
        q[use] = hist
        q[n:] = rot @ q[n:]
        df = rel[:, :, : len(q)] @ q

        a, _, _ = crossing(p, np.zeros(3), face, df, rest, g["axis"], g["radius"], hit["scale"] * 1.1)
        result.append(
            {
                "native_cutoff_Hz": cutoff,
                "residual_blocks": extra,
                "subdivision": subdivision,
                "time_s": station / rate,
                "stationary_rms_g": a * ref["stationary_reference_rms_g"],
            }
        )
    return result


def exclude_startup(g, sequence):
    """Certify only the physical time path, narrowing its correlated displacement bounds as needed."""

    def interval(first, last):
        part = sequence[first : last + 1]
        reference = (part.max(0) + part.min(0)) / 2
        moved = dict(
            g, p=g["p"] + g["pm"] @ reference, full_cell=g["full_cell"] + g["full_modes"] @ reference
        )
        try:
            result = certify(moved, part - reference, 1)
            return [
                {
                    "start": first,
                    "end": last,
                    "depth": len(result["unresolved_per_depth"]),
                    "broad_phase_pairs": result["broad_phase_pairs"],
                }
            ]
        except ValueError as exc:
            if last - first <= 1:
                raise ValueError(f"Unresolved time interval {first} to {last}") from exc
        mid = (first + last) // 2
        return interval(first, mid) + interval(mid, last)

    return interval(0, len(sequence) - 1)


def initial_time(g, q, branch, axis):
    """Compare first touch at full input with the first recorded pocket unloading or spacer change."""
    points = read(AUDIT / f"{branch}_pocket_face_unloading.json")["axes"][axis]
    seats = read(AUDIT / f"{branch}_spacer_bearing.json")["axes"][axis]
    method = points["selected"]
    first_open = points["histories"][method]["first_point_ms"]
    seats = seats["integrations"][method.removesuffix("_4000")]
    times = [s["current_length"]["interpolated_ms"] for s in seats if s["current_length"]]
    previous_ms = min(first_open, *times) if times else first_open
    end = previous_ms * FS / 1000
    whole = int(np.floor(end))
    tail = q[whole] + (end - whole) * (q[whole + 1] - q[whole])
    prefix = np.vstack((q[: whole + 1], tail))
    # For prefix searches the dimensionless level ceiling is exactly the full input.
    hit = witness(g, prefix, 1, 1)
    if hit is None:
        return {
            "original_switch_ms": previous_ms,
            "exclusion": exclude_startup(g, prefix),
            "first_time_bracket_ms": [previous_ms, previous_ms],
            "open_point_crossing": None,
        }
    low, high = 0, hit["sample"]
    while high - low > 1:
        mid = (high + low) // 2
        repeat = witness(g, prefix[: mid + 1], 1, 1)
        if repeat is None:
            low = mid
        else:
            high = repeat["sample"]
            hit = repeat
    bounded = exclude_startup(g, prefix[: low + 1])
    ix = np.flatnonzero((g["element"] == hit["element"]) & (g["point"] == hit["point"])).item()
    j = np.flatnonzero(g["target_ids"] == hit["target"]).item()
    pos = g["p"][ix] + g["pm"][ix] @ prefix[low]
    face = g["f"][j] + g["fm"][j] @ prefix[low]
    step = prefix[high] - prefix[low]
    fraction, uv, error = crossing(
        pos, g["pm"][ix] @ step, face, g["fm"][j] @ step, g["original"][j : j + 1], g["axis"], g["radius"], 1
    )
    upper = min(high, end)
    return {
        "original_switch_ms": previous_ms,
        "exclusion": bounded,
        "first_time_bracket_ms": [low * 1000 / FS, (low + fraction * (upper - low)) * 1000 / FS],
        "open_point_crossing": {
            "sample_interval": [int(low), int(high)],
            "element": hit["element"],
            "point": hit["point"],
            "target": hit["target"],
            "target_uv": uv.tolist(),
            "interval_fraction": fraction,
            "coincidence_error_mm": error,
        },
    }


def run(branch):
    path = AUDIT / f"{branch}_vibration_level.json"
    baseline = read(path)
    bp = AUDIT / f"{branch}_contact_vibration_basis.json"
    verified(bp, baseline["basis_audit_sha256"])
    proof = read(bp)
    file = CACHE / (branch + "_basis") / f"coupled_contact_b{proof['residual_blocks']}" / "basis.npz"
    verified(file, proof["basis_sha256"])
    with np.load(file) as z:
        data = {
            key: z[key]
            for key in (
                "nodes",
                "positions",
                "skin",
                "frequency",
                "drive",
                "labels",
                "middle",
                "block_width",
                "extra_K",
                "ports",
            )
        }
    static_check = AUDIT / f"{branch}_cellpush_swept_points.json"
    g = lock_geometry(branch, data, read(static_check))
    n = len(data["frequency"])
    print(
        branch,
        "open",
        len(g["p"]),
        "projected pairs",
        len(g["i"]),
        "min nm",
        min(g["gap"]) * 1e6,
        flush=True,
    )
    axes = {}
    for ax, axis in enumerate("XYZ"):
        ref = baseline["axes"][axis]
        limit = ref["first_with_exact_spacer_lengths"]
        if ref["native_MCF_sha256"]:
            file = ROOT / ".runtime/archive" / CAMPAIGN / f"{branch}_motion_{axis}" / "file.mcf"
            verified(file, ref["native_MCF_sha256"])
            q = native_series(file, data["frequency"])
        else:
            file = ROOT / ".runtime/motion_loads" / (axis + ".txt")
            verified(file, ref["input_sha256"])
            t, load = np.loadtxt(file, skiprows=1).T
            tt, wave, rms = excitation(axis)
            np.testing.assert_allclose(load, wave, rtol=1e-10, atol=1e-9)
            np.testing.assert_allclose(t, tt, rtol=0, atol=5.1e-13)
            assert abs(rms - ref["stationary_reference_rms_g"]) < 1e-10
            q = np.column_stack(
                [
                    linear_input_displacement(f, v, load, 1 / FS)
                    for f, v in zip(data["frequency"], data["drive"][:n, ax], strict=True)
                ]
            )
        assert q.shape == (9 * FS + 1, n) and np.isfinite(q).all()
        hit = witness(g, q, ref["stationary_reference_rms_g"], limit["scale"])
        print(axis, "limit", limit["stationary_rms_g"], "hit", hit, flush=True)
        bound = 0.99 * hit["scale"] if hit else limit["scale"]
        certificate = certify(g, q, bound)
        certificate["stationary_rms_g"] = bound * ref["stationary_reference_rms_g"]
        print("certificate", certificate, flush=True)
        controls = repeat_crossing(g, data, hit, axis, ref, proof["residual_blocks"]) if hit else []
        print("witness variations", controls, flush=True)
        startup = initial_time(g, q, branch, axis)
        print("full amplitude", axis, startup["first_time_bracket_ms"], flush=True)
        axes[axis] = {
            "reference_input_startup": startup,
            "witness_variations": controls,
            "motion_source": ref["selected"],
            "input_sha256": ref["input_sha256"],
            "native_MCF_sha256": ref["native_MCF_sha256"],
            "previous_monitored_change": limit,
            "exclusion": certificate,
            "contact_witness": hit,
        }
    write_json(
        AUDIT / f"{branch}_open_pocket_level.json",
        {
            "branch": branch,
            "modal_rst_sha256": proof["modal_rst_sha256"],
            "basis_sha256": proof["basis_sha256"],
            "previous_vibration_level_sha256": digest(path),
            "static_geometry_check_sha256": digest(static_check),
            "initially_open_points": len(g["p"]),
            "closed_middle_cell_triangles": len(g["full_cell"]),
            "duration_s": 9,
            "samples": 9 * FS + 1,
            "geometric_tolerance_mm": TOL_MM,
            "axes": axes,
            "scope": "Independent moving-geometry calculation on the locked linear modal response. Exclusion covers "
            "every initially open middle-pocket Gauss station against the whole quadratic cell boundary, at every "
            "recorded time and every amplitude up to the stated limit. Relative control positions interpolate "
            "linearly between time samples if the modal coordinates themselves are interpolated linearly. Other "
            "interfaces and unsampled positions on the PLA surface can move first. No material limit is inferred.",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branches", nargs="+", choices=BRANCHES)
    for branch in parser.parse_args().branches:
        run(branch)

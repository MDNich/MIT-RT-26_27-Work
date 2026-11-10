"""Check how an assumed mean M4 tension of 1 N changes spacer and pocket response under board-normal vibration."""

import argparse

import numpy as np
from film_cell_timestep import linear_input_displacement
from film_identity import digest, verified, write_json
from scipy.linalg import eigh
from seeded_motion import FS, excitation
from snug_board_pull import AUDIT, ROOT, read
from snug_contact_vibration import BRANCHES, CACHE, coordinates
from snug_open_pocket_level import (
    certify,
    crossing,
    lock_geometry,
    startup_before_switch,
    witness,
)
from snug_pocket_faces import SHAPE
from snug_pocket_sampling import candidates, project
from snug_vibration_level import exact_response, limits


def open_points(
    branch,
    data,
    cache,
    endpoint_file,
    frequency,
    factors,
    rotation,
    extra_rotation,
    load,
    rms,
    ports,
    previous,
    rate,
):
    """Test previously clear stations on the exact tightened skin at each recorded time."""
    with np.load(cache) as z:
        view = {key: z[key] for key in ("nodes", "middle", "skin", "labels")}
    with np.load(endpoint_file) as end:
        np.testing.assert_array_equal(end["nodes"], view["nodes"])
        view["positions"] = end["positions"]
    view["frequency"] = frequency
    static_source = read(AUDIT / f"{branch}_cellpush_swept_points.json")
    g = lock_geometry(branch, view, static_source)
    q = np.empty((len(load), len(frequency)))
    for i, (f, d) in enumerate(zip(frequency, factors, strict=True)):
        q[:, i] = linear_input_displacement(f, d, load, 1 / rate)
    n = len(data["frequency"])
    for start in range(0, len(q), 16384):
        sl = slice(start, start + 16384)
        converted = q[sl] @ rotation.T
        converted[:, n:] = converted[:, n:] @ extra_rotation.T
        np.testing.assert_allclose(
            converted @ data["ports"][: len(frequency)], q[sl] @ ports, rtol=1e-8, atol=1e-13
        )
        q[sl] = converted
    first = previous["first_monitored"]
    hit = witness(g, q, rms, first["scale"], rate)
    limit = hit["scale"] * 0.99 if hit else first["scale"]
    certificate = certify(g, q, limit)
    released_site = None
    if first["transition"] == "seats" and not first["label"].startswith("spacer"):
        element, point = map(int, first["label"].split("."))
        face = g["case_faces"][np.flatnonzero(g["case_ids"] == element).item()]
        weights = SHAPE[:, point - 1]
        position = 1000 * weights @ view["positions"][face]
        modes = 1000 * np.einsum("i,icm->cm", weights, view["skin"][face, :, : len(frequency)])
        at = first["scale"] * q[first["sample"]]
        moved = g["f"] + g["fm"] @ at
        gaps = []
        for sample, patch in ((position, g["f"]), (position + modes @ at, moved)):
            _, ids = candidates(
                sample[None],
                np.zeros(1),
                patch,
                np.zeros(patch.shape[:2]),
                g["axis"],
                g["radius"],
                g["original"],
            )
            distance, inside, _ = project(
                np.repeat(sample[None], len(ids), axis=0),
                patch[ids],
                g["original"][ids],
                g["axis"],
                g["radius"],
                False,
            )
            assert inside.sum() == 1
            gaps.append(float(distance[inside].item() * 1e6))
        face_id = ids[inside].item()
        displacement = q[first["sample"]]
        found = crossing(
            position,
            modes @ displacement,
            g["f"][face_id],
            g["fm"][face_id] @ displacement,
            g["original"][face_id : face_id + 1],
            g["axis"],
            g["radius"],
            1.2 * first["scale"],
        )
        assert found is not None
        released_site = {
            "fixed_tangent_geometric_contact_at_same_sample_rms_g": float(found[0] * rms),
            "coincidence_error_mm": float(found[2]),
            "label": first["label"],
            "signed_radial_gap_after_tightening_nm": gaps[0],
            "signed_radial_gap_at_predicted_seating_nm": gaps[1],
            "positive_direction": "clearance on the quadratic mesh",
        }
    observed = hit or first
    start = startup_before_switch(g, q, previous["first_time_at_full_input_ms"], rate)
    return {
        "formerly_loaded_site_geometry": released_site,
        "initially_open_points": len(g["p"]),
        "closed_cell_triangles": len(g["full_cell"]),
        "lowest_level_bracket_rms_g": [limit * rms, observed["stationary_rms_g"]],
        "contact_witness": hit,
        "exclusion": certificate,
        "reference_input_startup": start,
    }


def run(branch):
    static_path = AUDIT / f"{branch}_screw_preload_path.json"
    static = read(static_path)
    state = static["intervals"][-1]
    assert abs(state["mean_shank_tension_N"] - 1) < 1e-8 and not any(
        s["new_point"] for s in static["intervals"]
    )
    original_path = AUDIT / f"{branch}_vibration_level.json"
    original = read(original_path)
    basis_path = AUDIT / f"{branch}_contact_vibration_basis.json"
    verified(basis_path, original["basis_audit_sha256"])
    basis = read(basis_path)
    cache = CACHE / (branch + "_basis") / f"coupled_contact_b{basis['residual_blocks']}" / "basis.npz"
    verified(cache, basis["basis_sha256"])
    with np.load(cache) as src:
        data = {
            k: src[k] for k in ("frequency", "block_width", "extra_K", "drive", "ports", "k", "g", "labels")
        }
    assert static["native_modal_rst_sha256"] == basis["modal_rst_sha256"] == original["modal_rst_sha256"]
    np.testing.assert_array_equal(data["labels"], static["labels"])
    signed = np.array(state["signed_compression_nm"]) * 1e-9
    k = data["k"]
    old = data["g"] > 0
    active = signed > 0
    assert np.all(active[-4:]) and np.all(signed != 0)
    np.testing.assert_array_equal(data["labels"][active], state["bearing_inside_interval"])
    np.testing.assert_allclose(k * np.maximum(signed, 0), state["pocket_and_spacer_N"], atol=1e-8)
    spacer_path = AUDIT / f"{branch}_spacer_sensitivity.json"
    verified(spacer_path, static["previous_spacer_sensitivity_sha256"])
    target_freq = read(spacer_path)["conditional_support_states"]["all_bearing"]["first_frequencies_Hz"][:4]
    record = original["axes"]["Z"]
    input_file = ROOT / ".runtime/motion_loads/Z.txt"
    verified(input_file, record["input_sha256"])
    t, wave = np.loadtxt(input_file, skiprows=1).T
    tt, load, rms = excitation("Z")
    np.testing.assert_allclose(t, tt, rtol=0, atol=5.1e-13)
    np.testing.assert_allclose(wave, load, rtol=1e-10, atol=1e-9)
    known = original["axes"]["Z"]
    stages = {}
    for blocks in (2, basis["residual_blocks"]):
        omega, port, drive, extra_rotation = coordinates(data, blocks)
        reconstructed = data["g"] + (port / omega[:, None]).T @ (
            (port / omega[:, None]) @ state["equivalent_port_load_N"]
        )
        static_error_nm = max(abs(reconstructed - signed)) * 1e9
        assert static_error_nm < 0.05, static_error_nm
        # All-seat control uses a second, unreduced eigenanalysis with the original pocket contacts held at lock.
        diag = np.diag(omega**2)
        seats = np.r_[old[:-4], np.ones(4, bool)]

        def stiffness(mask, diag=diag, port=port):
            update = (mask.astype(float) - old) * k
            return diag + (port * update) @ port.T

        freq_control = np.sqrt(eigh(stiffness(seats), eigvals_only=True, subset_by_index=(0, 3))) / (
            2 * np.pi
        )
        np.testing.assert_allclose(freq_control, target_freq, rtol=8e-4, atol=0.001)
        values, rot = eigh(stiffness(active))
        assert np.all(values > 0)
        f = np.sqrt(values) / (2 * np.pi)
        shapes = rot.T @ port
        factors = rot.T @ drive[:, 2]
        for fine in (1, 2) if blocks == basis["residual_blocks"] else (1,):
            nt = (len(wave) - 1) * fine + 1
            signal = wave if fine == 1 else np.interp(np.arange(nt) / fine, np.arange(len(wave)), wave)
            history = exact_response(f, factors, shapes, signal, FS * fine)
            levels = limits(history, {"g": signed, "k": k, "labels": data["labels"]}, FS * fine, rms)
            selected = levels["first"]
            start = np.flatnonzero(np.any((signed + history) * signed <= 0, axis=1))
            assert len(start) and start[0] > 0
            j = int(start[0])
            adjacent = signed + history[j - 1 : j + 1]
            switches = np.flatnonzero(adjacent[0] * adjacent[1] <= 0)
            fractions = adjacent[0, switches] / (adjacent[0, switches] - adjacent[1, switches])
            m = fractions.argmin()
            stages[f"blocks{blocks}_sub{fine}"] = {
                "first_four_natural_frequencies_Hz": f[:4].tolist(),
                "control_first_four_Hz": freq_control.tolist(),
                "maximum_static_compression_error_nm": static_error_nm,
                "first_monitored": selected,
                "first_pocket": levels["first_pocket"],
                "first_spacer": levels["first_spacer"],
                "pocket_compression_at_first_N": levels["pocket_normal_force_at_first_N"],
                "first_time_at_full_input_ms": float(1000 * (j - 1 + fractions[m]) / (FS * fine)),
                "first_site_at_full_input": str(data["labels"][switches[m]]),
                "individual_switches": levels["points_and_spacers"],
            }
            endpoint_file = cache.parent / "screw_preload_skin.npz"
            verified(endpoint_file, static["endpoint_skin_sha256"])
            previous = stages[f"blocks{blocks}_sub{fine}"]
            previous["open_point_check"] = open_points(
                branch,
                data,
                cache,
                endpoint_file,
                f,
                factors,
                rot,
                extra_rotation,
                signal,
                rms,
                shapes,
                previous,
                FS * fine,
            )
    ref = stages[f"blocks{basis['residual_blocks']}_sub1"]
    for trial in stages.values():
        for key in ("first_monitored", "first_spacer", "first_pocket"):
            assert trial[key]["label"] == ref[key]["label"]
            np.testing.assert_allclose(trial[key]["scale"], ref[key]["scale"], rtol=0.01)
        geo = trial["open_point_check"]
        prior = ref["open_point_check"]
        np.testing.assert_allclose(
            geo["lowest_level_bracket_rms_g"], prior["lowest_level_bracket_rms_g"], rtol=0.01
        )
        for key in ("element", "point", "target"):
            assert (geo["contact_witness"] or {}).get(key) == (prior["contact_witness"] or {}).get(key)
        assert (
            abs(
                geo["reference_input_startup"]["first_time_bracket_ms"][-1]
                - prior["reference_input_startup"]["first_time_bracket_ms"][-1]
            )
            <= 1000 / FS
        )
    write_json(
        AUDIT / f"{branch}_preloaded_vibration.json",
        {
            "branch": branch,
            "screw_preload_sha256": digest(static_path),
            "native_basis_sha256": basis["modal_rst_sha256"],
            "baseline_levels_sha256": digest(original_path),
            "reduced_basis_sha256": basis["basis_sha256"],
            "unreduced_all_seat_modal_check_sha256": digest(spacer_path),
            "input_sha256": record["input_sha256"],
            "samples": len(t),
            "duration_s": float(t[-1]),
            "stationary_reference_rms_g": rms,
            "base_axis": "Z",
            "previously_monitored_limit_g": known["first_with_exact_spacer_lengths"]["stationary_rms_g"],
            "methods": stages,
            "selected": f"blocks{basis['residual_blocks']}_sub1",
            "scope": "Independent small-motion relinearization about the 1 N mean shank-tension state. "
            "Two-percent modal damping and the original time history are retained. The listed switch levels "
            "apply to pocket points that were loaded at the original bolt lock and to the four now-bearing "
            "spacers. The separate geometry check covers every originally clear middle-pocket point against the complete cell. Other interfaces and points between quadrature stations can change earlier. Later individual "
            "thresholds are conditional on continuing with the tightened tangent and do not describe impact or fatigue.",
        },
    )
    print(
        branch,
        ref["first_monitored"],
        ref["first_spacer"],
        ref["first_four_natural_frequencies_Hz"][:1],
        flush=True,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("branches", nargs="+", choices=BRANCHES)
    for name in p.parse_args().branches:
        run(name)

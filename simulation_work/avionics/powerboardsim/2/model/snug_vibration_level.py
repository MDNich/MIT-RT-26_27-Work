"""Scale each complete seeded waveform to the first change at a monitored pocket point or spacer."""

import argparse

import numpy as np
from audit_local import read
from audit_motion import native_series
from basis_comparison import field_files
from case_stress import source
from film_cell_timestep import linear_input_displacement, ramp_control
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from motion_surface import displacement_basis
from seeded_motion import FS, excitation, participation
from snug_board_pull import AUDIT, CAMPAIGN, ROOT
from snug_contact_vibration import BRANCHES, CACHE, coordinates
from snug_spacer_bearing import PILOTS


def exact_response(frequency, factors, shapes, load, rate):
    """Integrate independent damped oscillators with the piecewise-linear sampled acceleration."""
    result = np.zeros((len(load), shapes.shape[1]))
    for start in range(0, len(frequency), 8):
        block = slice(start, start + 8)
        q = np.column_stack(
            [
                linear_input_displacement(f, factor, load, 1 / rate)
                for f, factor in zip(frequency[block], factors[block], strict=True)
            ]
        )
        result += q @ shapes[block]
    return result


def limits(delta, data, rate, reference_rms):
    """For each contact maximize the fraction of its initial gap or compression used per input amplitude."""
    baseline, stiffness, labels = data["g"], data["k"], data["labels"]
    assert np.isfinite(delta).all() and np.all(baseline != 0) and np.max(abs(delta[0])) < 1e-14
    states = []
    for i, label in enumerate(labels):
        used = -delta[:, i] / baseline[i]
        j = int(used.argmax())
        if used[j] <= 0:
            states.append(None)
            continue
        amplitude = float(1 / used[j])
        signed = baseline + amplitude * delta[j]
        assert abs(signed[i]) < 1e-10 * abs(baseline[i])
        assert np.min(1 - (amplitude * (1 - 1e-7)) * used) > 0
        assert 1 - amplitude * (1 + 1e-7) * used[j] < 0
        states.append(
            {
                "label": str(label),
                "transition": "unloads" if baseline[i] > 0 else "seats",
                "scale": amplitude,
                "stationary_rms_g": amplitude * reference_rms,
                "sample": j,
                "time_s": j / rate,
            }
        )

    def smallest(group):
        eligible = [s for s in group if s is not None]
        return min(eligible, key=lambda s: s["scale"]) if eligible else None

    first = smallest(states)
    assert first is not None
    signed = baseline + first["scale"] * delta[first["sample"]]
    assert np.all(signed / baseline >= -1e-9)
    pocket = np.maximum(0, signed[:-4]) * stiffness[:-4]
    return {
        "first": first,
        "first_pocket": smallest(states[:-4]),
        "first_spacer": smallest(states[-4:]),
        "pocket_normal_force_at_first_N": float(pocket.sum()),
        "points_and_spacers": states,
    }


def check_startup(delta, data, face, spacer, axis, method):
    """Recover previously published full-amplitude switches using independent native element and pilot readbacks."""
    initial = data["g"]
    known = face["axes"][axis]["histories"][method + "_4000"]["each_point"]
    sample_by_label = {
        f"{p['element']}.{p['point']}": r["end_sample"] if r else None
        for p, r in zip(face["integration_points"], known, strict=True)
    }
    for i, r in enumerate(spacer["axes"][axis]["integrations"][method]):
        entry = r["projected_increment"]
        sample_by_label[f"spacer {i + 1}"] = entry["sample"] if entry else None
    assert set(sample_by_label) == set(data["labels"]) and spacer["samples"] == round(0.04 * FS) + 1
    for label, j in sample_by_label.items():
        (ix,) = np.flatnonzero(data["labels"] == label)
        switches = np.flatnonzero((initial[ix] + delta[: spacer["samples"], ix]) * initial[ix] <= 0)
        assert (int(switches[0]) if len(switches) else None) == j, (label, axis, method, j)
    return sum(v is not None for v in sample_by_label.values())


def finite_seat_limits(vectors, length, dxyz, reference_rms):
    """Solve for zero change from the original spacer length at every recorded time and seat."""
    output = []
    for i, (v, L) in enumerate(zip(vectors, length, strict=True)):
        d = dxyz[:, 3 * i : 3 * i + 3]
        a = np.einsum("ij,ij->i", d, d)
        b = d @ v
        c = (np.linalg.norm(v) - L) * (np.linalg.norm(v) + L)
        disc = b * b - a * c
        roots = np.full(len(d), np.inf)
        if c > 0:
            take = (a > 0) & (b < 0) & (disc >= 0)
            roots[take] = c / (-b[take] + np.sqrt(disc[take]))
        else:
            take = (a > 0) & (b >= 0)
            roots[take] = -c / (b[take] + np.sqrt(disc[take]))
            take = (a > 0) & (b < 0)
            roots[take] = (-b[take] + np.sqrt(disc[take])) / a[take]
        j = int(roots.argmin())
        assert np.isfinite(roots[j])
        assert abs(np.linalg.norm(v + roots[j] * d[j]) - L) < 1e-14

        before, after = roots[j] * (1 - 1e-6), roots[j] * (1 + 1e-6)
        assert ((c + before * (2 * b + a * before)) / c).min() > 0
        assert (c + after * (2 * b[j] + a[j] * after)) / c < 0
        output.append(
            {
                "label": f"spacer {i + 1}",
                "scale": float(roots[j]),
                "stationary_rms_g": float(roots[j] * reference_rms),
                "sample": j,
                "time_s": j / FS,
            }
        )
    return output


def run(branch):
    proof_path = AUDIT / f"{branch}_contact_vibration_basis.json"
    proof = read(proof_path)
    static_path = AUDIT / f"{branch}_spacer_pocket_pull.json"
    verified(static_path, proof["static_contact_check_sha256"])
    static = read(static_path)
    face_path = AUDIT / f"{branch}_pocket_face_unloading.json"
    spacer_path = AUDIT / f"{branch}_spacer_bearing.json"
    verified(face_path, static["face_preload_sha256"])
    verified(spacer_path, static["seat_preload_sha256"])
    face, spacer = read(face_path), read(spacer_path)
    modal, folder, raw = source(branch + "_basis", CAMPAIGN)
    assert (
        modal["rst_sha256"] == proof["modal_rst_sha256"] == face["modal_rst_sha256"] == spacer["modal_rst_sha256"]
    )
    if face["static_rst_sha256"] != spacer["static_rst_sha256"]:
        repeat = read(AUDIT / f"{branch}_pocket_force_repeat_check.json")
        assert branch == "snug125_nylon" and repeat["repeat_rst_sha256"] == face["static_rst_sha256"]
        assert repeat["locked_solid_equilibrium_sha256"] == face["locked_equilibrium_sha256"]
        assert repeat["maximum_displacement_difference_m"] < 1e-12
    assert read(ROOT / "validation/global" / f"{branch}_static.json")["rst_sha256"] == spacer["static_rst_sha256"]
    blocks = proof["residual_blocks"]
    path = CACHE / (branch + "_basis") / f"coupled_contact_b{blocks}" / "basis.npz"
    verified(path, proof["basis_sha256"])
    with np.load(path) as a:
        data = {k: a[k] for k in ("frequency", "block_width", "extra_K", "ports", "drive", "labels", "g", "k")}
    freq = data["frequency"]
    n = len(freq)
    np.testing.assert_array_equal(data["labels"], static["contact_labels"])
    np.testing.assert_allclose(data["g"] * 1e6, static["initial_compression_um"], atol=1e-12)
    np.testing.assert_allclose(data["k"], static["compression_slope_N_per_m"])
    basis = displacement_basis(raw, PILOTS, field_files(modal["case"], CAMPAIGN, modal["rst_sha256"], n))
    delta_xyz = np.diff(basis.reshape(n, 4, 2, 3), axis=2)[:, :, 0]
    # The original bolt-lock assembly defines the four end vectors and unstrained seat lengths.
    length = np.array(spacer["unstrained_grip_m"])
    v = np.diff(raw.mesh.nodes[positions(raw.mesh.nnum, PILOTS)].reshape(4, 2, 3), axis=1)[:, 0]
    np.testing.assert_allclose(length - np.linalg.norm(v, axis=1), data["g"][-4:], rtol=0, atol=1e-15)
    unit = v / np.linalg.norm(v, axis=1)[:, None]
    seat_shapes = -np.einsum("msd,sd->ms", delta_xyz, unit)
    np.testing.assert_allclose(seat_shapes, data["ports"][:n, -4:], rtol=1e-6, atol=1e-10)
    listing = folder / "solve.out"
    verified(listing, proof["modal_listing_sha256"])
    assert ramp_control() < 1e-6
    axes = {}
    for j, ax in enumerate("XYZ"):
        evidence = read(ROOT / "validation/independent_motion" / f"{branch}_motion_{ax}.json")
        assert (
            evidence["basis_rst_sha256"] == modal["rst_sha256"]
            and evidence["modal_listing_sha256"] == proof["modal_listing_sha256"]
        )
        input_path = ROOT / ".runtime/motion_loads" / f"{ax}.txt"
        verified(input_path, evidence["input_sha256"])
        t, load = np.loadtxt(input_path, skiprows=1).T
        tt, test, rms = excitation(ax)
        np.testing.assert_allclose(t, tt, atol=5.1e-13, rtol=0)
        np.testing.assert_allclose(load, test, rtol=1e-10, atol=1e-9)
        gamma = participation(listing.read_text(errors="replace"), ax)
        np.testing.assert_allclose(gamma, data["drive"][:n, j], rtol=1e-7, atol=1e-12)
        h = data["ports"][:n]
        projected = exact_response(freq, gamma, np.column_stack((h, delta_xyz.reshape(n, -1))), load, FS)
        exact = projected[:, : len(data["g"])]
        methods = {"exact_4000": limits(exact, data, FS, rms)}
        startup = {"exact": check_startup(exact, data, face, spacer, ax, "exact_linear_input")}
        dxyz = projected[:, len(data["g"]) :]
        direct = ROOT / "validation/motion" / f"{branch}_motion_{ax}.json"
        native_sha = None
        if direct.is_file():
            ref = read(direct)
            native_sha = ref["mcf_sha256"]
            assert (
                ref["basis_rst_sha256"] == modal["rst_sha256"] and ref["input_sha256"] == evidence["input_sha256"]
            )
            mcf = ROOT / ".runtime/archive" / CAMPAIGN / ref["case"] / "file.mcf"
            verified(mcf, native_sha)
            q = native_series(mcf, freq)
            native = q @ h
            methods["native_4000"] = limits(native, data, FS, rms)
            startup["native"] = check_startup(native, data, face, spacer, ax, "native")
            dxyz = q @ delta_xyz.reshape(n, -1)
            del q, native
        selected = "native_4000" if native_sha else "exact_4000"
        finite = finite_seat_limits(v, length, dxyz, rms)
        reference_method = "native" if native_sha else "exact_linear_input"
        for seat, (a, b, earlier) in enumerate(
            zip(
                finite,
                methods[selected]["points_and_spacers"][-4:],
                spacer["axes"][ax]["integrations"][reference_method],
                strict=True,
            )
        ):
            a["relative_to_projected_length"] = a["scale"] / b["scale"] - 1
            full_length = np.linalg.norm(v[seat] + dxyz[: spacer["samples"], 3 * seat : 3 * seat + 3], axis=1)
            switches = np.flatnonzero((full_length < length[seat]) != (np.linalg.norm(v[seat]) < length[seat]))
            previous = earlier["current_length"]
            assert (int(switches[0]) if len(switches) else None) == (previous["sample"] if previous else None)
        exact_first = min([methods[selected]["first_pocket"], *finite], key=lambda entry: entry["scale"])
        use = freq <= 3500
        methods["exact_3500"] = limits(exact_response(freq[use], gamma[use], h[use], load, FS), data, FS, rms)
        # Corrections use the verified residual basis of the installed assembly, held at bolt-lock topology.
        # The native retained part is common, so only the additional oscillators need reintegration.
        double_load = np.interp(np.arange(2 * len(load) - 1) / 2, np.arange(len(load)), load)
        for b in (2, blocks):
            omega, port, drive, _ = coordinates(data, b)
            extra = exact_response(omega[n:] / (2 * np.pi), drive[n:, j], port[n:], load, FS)
            methods[f"enriched_{b}"] = limits(exact + extra, data, FS, rms)
            if b == blocks:
                full = exact_response(omega / (2 * np.pi), drive[:, j], port, double_load, 2 * FS)
                np.testing.assert_allclose(full[::2], exact + extra, rtol=1e-7, atol=1e-12)
                methods[f"enriched_{b}_half_interval"] = limits(full, data, 2 * FS, rms)
                del full
            del extra
        axes[ax] = {
            "input_sha256": evidence["input_sha256"],
            "native_MCF_sha256": native_sha,
            "selected": selected,
            "stationary_reference_rms_g": rms,
            "actual_window_rms_g": float(np.sqrt(np.mean(load**2)) / 9.806),
            "prior_full_amplitude_switches_reproduced": startup,
            "exact_pilot_length_seat_limits": finite,
            "first_with_exact_spacer_lengths": exact_first,
            "methods": methods,
        }
        print(
            branch,
            ax,
            [(k, v["first"]["label"], round(v["first"]["stationary_rms_g"], 8)) for k, v in methods.items()],
            flush=True,
        )
    write_json(
        AUDIT / f"{branch}_vibration_level.json",
        {
            "branch": branch,
            "basis_audit_sha256": digest(proof_path),
            "modal_rst_sha256": modal["rst_sha256"],
            "pocket_audit_sha256": digest(face_path),
            "spacer_audit_sha256": digest(spacer_path),
            "installed_pocket_compression_N": float((data["k"][:-4] * data["g"][:-4]).sum()),
            "duration_s": 9,
            "sample_rate_Hz": FS,
            "samples": 9 * FS + 1,
            "axes": axes,
            "scope": "Separate, uniformly scaled nine-second X/Y/Z inputs at the audited stress-free M4 assembly. "
            "The first monitored change is the earliest in amplitude among originally loaded middle-pocket "
            "points and four spacer seats, over all sampled times. Additional contacts can change the "
            "response sooner. RMS refers to the stationary portion of the original periodic input. "
            "These thresholds test the assumed contact state and give no material strength or fatigue limit.",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branches", nargs="+", choices=BRANCHES)
    args = parser.parse_args()
    for branch in args.branches:
        run(branch)

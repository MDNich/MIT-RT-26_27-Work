"""Check the first 31.25 ms of vibration with the original points and four spacer seats changing state."""

import argparse

import numpy as np
from early_cell_clearance import bezier, subdivision_weights
from film_identity import digest, verified, write_json
from scipy.linalg import expm
from scipy.optimize import brentq
from seeded_motion import FS
from snug_board_pull import AUDIT, CAMPAIGN, ROOT, read
from snug_contact_vibration import BRANCHES, CACHE, coordinates
from snug_pocket_release import certify_pair
from snug_shell_drive_sampling import native_startup


def newmark(omega, B, k, g, gamma, samples, divisions, *, switch=True):
    dt = 1 / (FS * divisions)
    index = np.arange((len(samples) - 1) * divisions + 1)
    load = np.interp(index / divisions, np.arange(len(samples)), samples)
    assert load[0] == 0
    alpha = dt**2 / 4
    damp = 0.04 * omega
    diag = 1 / (1 + dt * damp / 2 + alpha * omega**2)
    kinv = diag[:, None] * B
    compliance = alpha * (B.T @ kinv)
    q = np.zeros(len(omega))
    v = q.copy()
    acc = q.copy()
    history = np.zeros((len(load), len(q)))
    installed = g > 0
    mask = installed.copy()
    transforms = {}
    work = 0.0
    dissipated = 0.0
    max_error = 0.0
    scale = 0.0
    max_iter = 0
    for i in range(1, len(load)):
        pred = q + dt * v + alpha * acc
        vs = v + dt * acc / 2
        a0 = diag * (-load[i] * gamma - damp * vs - omega**2 * pred)
        trial = g + B.T @ (pred + alpha * a0)
        if switch:
            for it in range(1, 20):
                key = mask.tobytes()
                if key not in transforms:
                    change = k * (mask.astype(float) - installed)
                    transforms[key] = np.linalg.solve(
                        np.eye(len(k)) + change[:, None] * compliance, np.diag(change)
                    )
                df = transforms[key] @ trial
                z = trial - compliance @ df
                updated = z > 0
                if np.array_equal(updated, mask):
                    break
                mask = updated
            else:
                raise ArithmeticError("Contact active set failed at sample " + str(i))
            max_iter = max(max_iter, it)
            acc = a0 - kinv @ df
        else:
            acc = a0
        new_q = pred + alpha * acc
        new_v = vs + dt * acc / 2
        mean_v = (new_v + v) / 2
        work -= float((load[i] + load[i - 1]) / 2 * gamma @ (new_q - q))
        dissipated += float(dt * (damp * mean_v) @ mean_v)
        q, v = new_q, new_v
        delta = B.T @ q
        energy = (v @ v + (omega * q) @ (omega * q)) / 2
        if switch:
            assert abs(z - (g + delta)).max() < 2e-15
            energy += 0.5 * np.sum(k * (mask.astype(float) - installed) * z**2)
        history[i] = q
        scale = max(scale, abs(work), energy)
        max_error = max(max_error, abs(energy + dissipated - work))
    return history, max_error / scale, max_iter


def exact_check(omega, B, k, g, gamma, load, divisions):
    """Independently advance each fixed contact state, locating the earliest switch within a step."""
    n = len(omega)
    dt = 1 / (divisions * FS)
    installed = g > 0
    count = (len(load) - 1) * divisions + 1
    acc = np.interp(np.arange(count) / divisions, np.arange(len(load)), load)
    state = np.zeros(2 * n + 3)
    state[-1] = 1
    result = np.zeros((count, n))
    mask = installed.copy()
    cache = {}
    switches = []

    def matrices(mask):
        key = mask.tobytes()
        if key not in cache:
            change = k * (mask.astype(float) - installed)
            A = np.zeros((2 * n + 3, 2 * n + 3))
            A[:n, n : 2 * n] = np.diag(omega)
            A[n : 2 * n, :n] = -np.diag(omega) - (B * change) @ (B / omega[:, None]).T
            A[n : 2 * n, n : 2 * n] = -np.diag(0.04 * omega)
            A[n : 2 * n, -3] = -gamma
            A[n : 2 * n, -1] = -B @ (change * g)
            A[-3, -2] = 1
            cache[key] = (A, expm(A * dt))
        return cache[key]

    cov = B / omega[:, None]
    for i in range(1, count):
        state[-3:-1] = [acc[i - 1], (acc[i] - acc[i - 1]) / dt]
        remain = dt
        for _ in range(20):
            A, advance = matrices(mask)
            end = (advance if remain == dt else expm(A * remain)) @ state
            end_gap = g + cov.T @ end[:n]
            swaps = np.flatnonzero((end_gap > 0) != mask)
            if not len(swaps):
                state = end
                break
            crossings = []
            for j in swaps:

                def gap(t, j=j, A=A, state=state):
                    return g[j] + cov[:, j] @ (expm(A * t) @ state)[:n]

                start = gap(0.0)
                if (start > 0) != mask[j]:
                    assert abs(start) < 3e-15
                    root = 0.0
                else:
                    root = brentq(gap, 0.0, remain, xtol=1e-15)
                crossings.append((root, int(j)))
            t = min(d for d, j in crossings)
            state = expm(A * t) @ state
            for time, j in crossings:
                if time - t < 1e-13:
                    mask[j] = ~mask[j]
                    switches.append(((i * dt - remain + t), j))
            remain -= t
            if remain < 1e-15:
                break
        else:
            raise ArithmeticError("Repeated transition at one instant")
        result[i] = state[:n] / omega
    return result, switches


def classification(q, B, k, g, dt):
    z = g + q @ B
    active = z > 0
    force = np.maximum(z, 0) * k
    change = np.any(active != active[0], axis=1)
    bare = np.all(~active[:, :-4], axis=1)
    start = np.flatnonzero(bare & ~np.r_[False, bare[:-1]])
    end = np.flatnonzero(~bare & np.r_[False, bare[:-1]])
    intervals = []
    for a in start:
        later = end[end > a]
        intervals.append([float(a * dt * 1000), float(later[0] * dt * 1000) if len(later) else None])
    near = -z[:, :-4].max(axis=1) * 1e9
    return (
        {
            "first_contact_change_ms": float(np.flatnonzero(change)[0] * dt * 1000)
            if change.any()
            else None,
            "whole_original_patch_open_intervals_ms": intervals,
            "peak_minimum_original_spring_opening_nm": float(near.max()),
            "peak_sum_of_pocket_compression_N": float(force[:, :-4].sum(1).max()),
            "peak_sum_of_spacer_compression_N": float(force[:, -4:].sum(1).max()),
            "fraction_samples_all_original_points_open": float(bare.mean()),
        },
        z,
        force,
    )


def run(branch):
    proof_path = AUDIT / f"{branch}_contact_vibration_basis.json"
    proof = read(proof_path)
    path = CACHE / (branch + "_basis") / f"coupled_contact_b{proof['residual_blocks']}"
    verified(path / "basis.npz", proof["basis_sha256"])
    with np.load(path / "basis.npz") as archive:
        data = {k: archive[k] for k in archive.files}
    n = proof["native_modes"]
    blocks = proof["residual_blocks"]
    k = data["k"]
    g = data["g"]
    results = {}
    sample = np.arange(2049)
    for j, axis in enumerate("XYZ"):
        evidence = read(ROOT / "validation/independent_motion" / (branch + "_motion_" + axis + ".json"))
        assert (
            evidence["basis_rst_sha256"] == proof["modal_rst_sha256"]
            and evidence["modal_listing_sha256"] == proof["modal_listing_sha256"]
        )
        input_file = ROOT / ".runtime/motion_loads" / (axis + ".txt")
        verified(input_file, evidence["input_sha256"])
        tt, load = np.loadtxt(input_file, skiprows=1, max_rows=len(sample)).T
        np.testing.assert_allclose(tt, sample / FS, atol=5.1e-13, rtol=0)
        spatial = {}
        temporal = {}
        previous = None
        for b in range(blocks + 1):
            om, B, drive, rotation = coordinates(data, b)
            q, en, _ = newmark(om, B, k, g, drive[:, j], load, 4)
            summary, _, forces = classification(q, B, k, g, 1 / (4 * FS))
            spatial[b] = {"outcomes": summary, "energy_relative_error": en}
            if previous is not None:
                spatial[b]["force_change_norm_per_column"] = np.linalg.norm(
                    forces - previous, axis=0
                ).tolist()
                spatial[b]["pocket_force_relative_RMS_change"] = float(
                    np.linalg.norm(forces[:, :-4] - previous[:, :-4]) / np.linalg.norm(forces[:, :-4])
                )
            previous = forces
            if b == 0:
                ref, _, _ = newmark(om, B, k, g, drive[:, j], load, 1, switch=False)
                if (ROOT / "validation/motion" / (branch + "_motion_" + axis + ".json")).exists():
                    native, source_id = native_startup(evidence, CAMPAIGN, data["frequency"], sample)
                    diff = np.linalg.norm(native - ref) / np.linalg.norm(native)
                    assert diff < 3e-5, diff
                else:
                    source_id = {}
                    diff = None
        qf, _, _ = newmark(om, B, k, g, drive[:, j], load, 4, switch=False)
        frozen = (g + qf @ B) * k
        previous_time = None
        for div in (1, 2, 4, 8, 16, 32, 64, 128):
            qt, en, its = newmark(om, B, k, g, drive[:, j], load, div)
            c, z, force = classification(qt, B, k, g, 1 / (div * FS))
            temporal[div] = {"outcomes": c, "energy_relative_error": en, "max_active_iterations": its}
            if previous_time is not None:
                relative = float(np.linalg.norm(force[::2] - previous_time) / np.linalg.norm(force[::2]))
                peak_error = abs(
                    c["peak_sum_of_pocket_compression_N"]
                    / temporal[div // 2]["outcomes"]["peak_sum_of_pocket_compression_N"]
                    - 1
                )
                temporal[div].update(
                    previous_force_relative_RMS_change=relative, pocket_peak_relative_change=peak_error
                )
                if div >= 8 and relative < 0.005 and peak_error < 0.008 and en < 2e-5:
                    break
            previous_time = force
        else:
            raise ArithmeticError(
                f"Time refinement unresolved for {branch} {axis}: {relative} and peak {peak_error}"
            )
        # Independent piecewise matrix exponentials and within-step contact roots.
        # Recheck both time resolution and the two largest spatial bases on this same input.
        exact_controls = {}
        for space in (blocks - 1, blocks):
            ex_omega, ex_B, ex_gamma, _ = coordinates(data, space)
            for step in (4,) if space < blocks else (2, 4):
                xe, ev = exact_check(ex_omega, ex_B, k, g, ex_gamma[:, j], load, step)
                signed = g + xe @ ex_B
                actual = k * np.maximum(0, signed[::step])
                key = f"b{space}_s{step}"
                exact_controls[key] = {
                    "transitions": len(ev),
                    "first_transition_ms": 1000 * ev[0][0],
                    "last_transition_ms": 1000 * ev[-1][0],
                    "peak_pocket_force_N": float((k[:-4] * np.maximum(0, signed[:, :-4])).sum(1).max()),
                }
                if space == blocks - 1:
                    space_check = actual
                elif step == 2:
                    step_check = actual
                else:
                    target = force[::div]
                    den = np.linalg.norm(actual)
                    exact_controls["independent_force_relative_RMS_error"] = float(
                        np.linalg.norm(actual - target) / den
                    )
                    exact_controls["exact_force_time_refinement"] = float(
                        np.linalg.norm(step_check - actual) / den
                    )
                    exact_controls["exact_pocket_force_spatial_refinement"] = float(
                        np.linalg.norm(space_check[:, :-4] - actual[:, :-4])
                        / np.linalg.norm(actual[:, :-4])
                    )
                    assert exact_controls["independent_force_relative_RMS_error"] < 0.009
                    assert exact_controls["exact_force_time_refinement"] < 0.009
        # At the greatest clearance of the least-open original point, test all three curved cell surfaces.
        witness = int(np.argmax(-z[:, :-4].max(axis=1)))
        snap = np.r_[qt[witness, :n], rotation @ qt[witness, n:]]
        dx = np.einsum("ijk,k->ij", data["skin"], snap)
        xyz = 1000 * (data["positions"] + dx)
        case = bezier(xyz[data["case"]])
        checks = {
            name: certify_pair(case, bezier(xyz[data[name]]), subdivision_weights())
            for name in ("left", "middle", "right")
        }
        assert not any(x["state"] == "unresolved" for x in checks.values())
        if checks["middle"]["state"] == "separated":
            from snug_surface_distance import surface_distance

            checks["middle"]["distance"] = surface_distance(case, bezier(xyz[data["middle"]]))
        # Store common time samples for publication and independent convergence checks.
        history = path / (axis + "_history.npz")
        np.savez(
            history,
            time_ms=sample / FS * 1000,
            point_and_spacer_force_N=force[::div],
            signed_compression_m=z[::div],
            installed_tangent_trial_force_N=frozen[::4],
            selected_time_s=witness / (div * FS),
            selected_q=snap,
            load=load,
        )
        results[axis] = {
            "input_sha256": evidence["input_sha256"],
            "native_coordinate_source": source_id,
            "frozen_native_coordinate_relative_error": diff,
            "outcomes": c,
            "exact_integration_checks": exact_controls,
            "substeps_per_input_sample": div,
            "spatial": spatial,
            "temporal": temporal,
            "selected_geometry": {
                "sample_index": witness,
                "dt_s": 1 / (div * FS),
                "time_ms": 1000 * witness / (div * FS),
                "surfaces": checks,
            },
            "history_sha256": digest(history),
        }
        print(
            branch,
            axis,
            c,
            "time_err",
            relative,
            "space_err",
            spatial[blocks]["pocket_force_relative_RMS_change"],
            {v: s["state"] for v, s in checks.items()},
            flush=True,
        )
    write_json(
        AUDIT / f"{branch}_contact_vibration.json",
        {
            "branch": branch,
            "basis_proof_sha256": digest(proof_path),
            "duration_ms": 1000 * sample[-1] / FS,
            "output_sample_rate_Hz": FS,
            "axes": results,
            "scope": "Independent reduced whole-board startup response. Original loaded pocket points and tab spacers can open and reclose. Other potential contacts are checked geometrically at selected times. Damping is held at 2% of critical in the installed modal basis.",
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("branch", choices=BRANCHES)
    run(p.parse_args().branch)

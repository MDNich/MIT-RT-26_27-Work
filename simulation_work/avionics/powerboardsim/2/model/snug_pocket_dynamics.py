"""Independent startup response of the installed aluminium mount with one unilateral contact spring."""

import argparse
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from case_stress import source
from dmp_board_matrix import assemble
from early_cell_clearance import outer_faces
from film_identity import digest, verified, write_json
from scipy.linalg import eigh, solve_triangular
from scipy.sparse import triu
from seeded_motion import FS, participation
from snug_board_flexibility import equation_modes
from snug_board_pull import AUDIT, BODIES, CAMPAIGN, ROOT, positions, read
from snug_board_tangent import TangentSolver, symmetric_product
from snug_pocket_release import contact_block

BRANCH = "snug125_aluminium"
OUTPUT = ROOT / ".runtime/post" / CAMPAIGN / (BRANCH + "_basis") / "unilateral_startup"
BASIS_PROOF = AUDIT / "aluminium_unilateral_reduction.json"
STUDY = AUDIT / "aluminium_unilateral_startup.json"


def residual_basis(basis, mass, stiffness, loads, factor, native_modes, blocks):
    """Mass-orthogonal block inverse iteration starting with the static load responses."""
    n0 = native_modes
    width = loads.shape[1]
    assert basis.shape[1] == n0 + width * blocks
    weighted = np.empty_like(basis, order="F")
    weighted[:, :n0] = mass @ basis[:, :n0]
    np.testing.assert_allclose(basis[:, :n0].T @ weighted[:, :n0], np.eye(n0), atol=1e-6)
    rhs = loads
    for j in range(blocks):
        start = n0 + width * j
        v = factor.solve(rhs)
        if j == 0:
            work = loads.T @ v
            assert np.linalg.norm(work - work.T) < 1e-9 * np.linalg.norm(work)
        for _ in range(2):
            v -= basis[:, :start] @ (weighted[:, :start].T @ v)
        mv = mass @ v
        scale = np.sqrt(np.einsum("ij,ij->j", v, mv))
        assert min(scale) > 0
        v /= scale
        mv /= scale
        gram = v.T @ mv
        lower = np.linalg.cholesky(0.5 * (gram + gram.T))
        basis[:, start : start + width] = solve_triangular(lower, v.T, lower=True).T
        weighted[:, start : start + width] = solve_triangular(lower, mv.T, lower=True).T
        rhs = weighted[:, start : start + width]
    mass_error = float(abs(basis.T @ weighted - np.eye(basis.shape[1])).max())
    assert mass_error < 1e-6
    extra = basis[:, n0:]
    products = symmetric_product(stiffness, extra)
    K = extra.T @ products
    return (K + K.T) / 2, basis[:, :n0].T @ products, work, mass_error


def reduce_model(matrices, library, blocks=4):
    modal, folder, rst = source(BRANCH + "_basis", CAMPAIGN)
    release_file = AUDIT / f"{BRANCH}_released_pocket_tangent.json"
    release = read(release_file)
    unload_file = AUDIT / f"{BRANCH}_pocket_unloading.json"
    unload = read(unload_file)
    assert release["single_contact_prediction"]["unloading_record_sha256"] == digest(unload_file)
    assert modal["rst_sha256"] == unload["modal_rst_sha256"] == release["modal_rst_sha256"]
    ledger = read(ROOT / ".runtime/receipts" / CAMPAIGN / modal["case"] / "archived.json")
    hashes = {row["name"]: row["sha256"] for row in ledger["files"]}
    keys, _, H, _, _ = contact_block(folder, rst, hashes, release["nonzero_contact_elements"])
    assert H.shape[1] == 1
    grid = rst.mesh
    order = np.argsort(grid.enum)
    (elem,) = release["nonzero_contact_elements"]
    cap = np.unique(grid.elem[order[positions(grid.enum[order], [elem])[0]]][10:18])
    resultant = np.array([H[(keys % 8 == i) & np.isin(keys // 8, cap), 0].sum() for i in range(3)])
    beta = float(-np.array(unload["opening_direction"]) @ resultant)
    # Orient the stiffness factor so increasing h^T u unloads the native pocket.
    H = H[:, 0] * np.sign(beta)
    beta = abs(beta)
    stiffness = release["single_contact_prediction"]["normal_spring_stiffness_N_per_m"]
    assert abs(beta**2 / stiffness - 1) < 1e-6
    d, free, _, _, transfer, K, M, identity = matrices
    assert identity["files"] == release["full_files_sha256"]
    labels = 8 * d[:, 0].astype(np.int64) + d[:, 1]
    order = np.argsort(labels)
    contact_eq = positions(free, order[positions(labels[order], keys)])
    h = np.zeros(len(free))
    h[contact_eq] = H
    mass = (M + triu(M, 1).T).tocsr()
    drive = mass @ (d[free, 1, None] == np.arange(3)).astype(float)
    loads = np.column_stack((h, drive))
    N = rst.nsets
    frequency = rst.time_values
    basis = np.empty((len(free), N + 4 * blocks), order="F")
    for i, mode in enumerate(equation_modes(BRANCH, modal, folder, rst, d, range(N))):
        basis[:, i] = mode[free]
    listing = folder / "solve.out"
    verified(listing, hashes["solve.out"])
    gamma = np.column_stack([participation(listing.read_text(errors="replace"), ax) for ax in "XYZ"])
    projected = basis[:, :N].T @ drive
    projection_error = np.linalg.norm(projected - gamma, axis=0) / np.linalg.norm(gamma, axis=0)
    assert projection_error.max() < 3e-5
    factor = TangentSolver(K, library)
    try:
        reduced_K, cross, work, mass_error = residual_basis(basis, mass, K, loads, factor, N, blocks)
    finally:
        factor.close()
    off_diagonal = float(
        abs(cross / (2 * np.pi * frequency[:, None] * np.sqrt(reduced_K.diagonal()))).max()
    )
    assert off_diagonal < 1e-6
    hshape = basis.T @ h
    native_recovery = read(ROOT / "validation/cell_attachment" / f"{BRANCH}.json")
    stored = folder.parents[2] / "post" / CAMPAIGN / modal["case"] / "attachment_modes.npz"
    verified(stored, native_recovery["shape_force_sha256"])
    with np.load(stored) as forces:
        p = np.array(unload["opening_direction"]) @ forces["middle_cell_pocket_force"]
    force_error = float(np.linalg.norm(beta * hshape[:N] - p) / np.linalg.norm(p))
    assert force_error < 1e-6
    surface = [outer_faces(rst, [m]) for m in (850, *BODIES)]
    nodes = np.unique(np.concatenate([s.ravel() for s in surface]))
    take = order[positions(labels[order], 8 * nodes[:, None] + np.arange(3))]
    fields = np.zeros((len(d), basis.shape[1] - N))
    fields[free] = basis[:, N:]
    fields += transfer @ fields
    OUTPUT.mkdir(parents=True, exist_ok=True)
    basis_file = OUTPUT / "reduction.npz"
    np.savez(
        basis_file,
        freq=frequency,
        h=hshape,
        beta=beta,
        preload=unload["projected_compression_N"][unload["selected_preload_source"]],
        residual_K=reduced_K,
        gamma=gamma,
        residual_gamma=basis[:, N:].T @ drive,
        nodes=nodes,
        fields=fields[take],
    )
    controls = []
    for k in range(blocks + 1):
        freq, coupling, _, _, _ = model_coordinates(basis_file, k)
        closed = (2 * np.pi * freq) ** 2
        retained = float(np.sum(coupling**2 / closed))
        open_Hz = np.sqrt(
            eigh(np.diag(closed) - np.outer(coupling, coupling), eigvals_only=True)[:6]
        ) / (2 * np.pi)
        reference = np.array([r["open_Hz"] for r in release["first_six_open_modes"]])
        if k:
            assert abs(retained / work[0, 0] - 1) < 1e-6 and max(abs(open_Hz - reference)) < 0.15
        controls.append(
            {
                "residual_vectors": 4 * k,
                "retained_static_contact_compliance_fraction": retained / work[0, 0],
                "first_six_open_Hz": open_Hz.tolist(),
                "max_open_frequency_error_Hz": float(max(abs(open_Hz - reference))),
            }
        )
    write_json(
        BASIS_PROOF,
        {
            "branch": BRANCH,
            "modal_rst_sha256": modal["rst_sha256"],
            "modal_listing_sha256": hashes["solve.out"],
            "release_sha256": digest(release_file),
            "unloading_sha256": digest(unload_file),
            "shape_force_sha256": native_recovery["shape_force_sha256"],
            "basis_sha256": digest(basis_file),
            "native_modes": N,
            "residual_blocks": blocks,
            "unreduced_contact_compliance": work[0, 0],
            "unit_load_static_work": work.tolist(),
            "max_modal_mass_error": mass_error,
            "normalized_cross_stiffness": off_diagonal,
            "native_force_operator_relative_error": force_error,
            "relative_base_participation_error": projection_error.tolist(),
            "open_mode_checks": controls,
            "scope": "Independent block reduction of the archived installed stiffness and mass, enriched with "
            "responses to one contact force and three translational inertia loads. Damping is assigned in the seated reduced modes.",
        },
    )
    print(
        "Reduction verified",
        controls[0]["retained_static_contact_compliance_fraction"],
        controls[-1]["max_open_frequency_error_Hz"],
        flush=True,
    )


def model_coordinates(path, blocks):
    with np.load(path) as data:
        k = 4 * blocks
        n = len(data["freq"])
        eigen, vectors = eigh(data["residual_K"][:k, :k])
        freq = np.r_[data["freq"], np.sqrt(eigen) / (2 * np.pi)]
        h = np.r_[data["h"][:n], vectors.T @ data["h"][n : n + k]]
        gamma = np.vstack((data["gamma"], vectors.T @ data["residual_gamma"][:k]))
        return freq, h, gamma, vectors, (float(data["beta"]), float(data["preload"]))


def prepare():
    folder = ROOT / ".runtime/archive" / CAMPAIGN / (BRANCH + "_basis")
    manifest = read(ROOT / ".runtime/receipts" / CAMPAIGN / folder.name / "archived.json")
    hashes = {row["name"]: row["sha256"] for row in manifest["files"]}
    with TemporaryDirectory() as tmp:
        library = Path(tmp) / "factor.dylib"
        subprocess.run(
            [
                "clang",
                "-O2",
                "-dynamiclib",
                "-framework",
                "Accelerate",
                str(Path(__file__).with_name("board_tangent_factor.c")),
                "-o",
                str(library),
            ],
            check=True,
        )
        reduce_model(assemble(folder, hashes), library)


def newmark(freq, h, beta, pre, gamma, load, substeps):
    """Implicit average-acceleration update with a scalar contact-state solution."""
    omega = 2 * np.pi * freq
    K = omega**2
    C = 0.04 * omega
    idx = np.arange((len(load) - 1) * substeps + 1)
    a = np.interp(idx / substeps, np.arange(len(load)), load)
    dt = 1 / (FS * substeps)
    inv = 1 / (1 + dt * C / 2 + dt**2 * K / 4)
    correction = inv * h
    den = 1 - dt**2 * (h @ correction) / 4
    assert den > 0 and a[0] == 0
    q = np.zeros_like(freq)
    v = q.copy()
    acc = q.copy()
    history = np.zeros((len(idx), len(q)))
    power = np.zeros((len(idx), 2))
    energy = np.zeros(len(idx))
    for i in range(1, len(idx)):
        guess = q + dt * v + dt**2 * acc / 4
        speed = v + dt * acc / 2
        acc = inv * (-gamma * a[i] - C * speed - K * guess)
        seated = guess + dt**2 * acc / 4
        excess = max(0.0, (h @ seated - pre / beta) / den)
        acc += correction * excess
        q = guess + dt**2 * acc / 4
        v = speed + dt * acc / 2
        history[i] = q
        power[i] = [-a[i] * (gamma @ v), v @ (C * v)]
        energy[i] = (v @ v + (K * q) @ q - excess**2) / 2
    integrated = np.sum(0.5 * (power[:-1] + power[1:]) * dt, axis=0)
    error = abs(energy[-1] - integrated[0] + integrated[1]) / max(abs(integrated[0]), energy.max())
    return history, float(error)


def exact_response(freq, h, beta, pre, gamma, load, substeps):
    """Advance each constant contact state with a matrix exponential, locating changes inside the step."""
    from scipy.linalg import expm
    from scipy.optimize import brentq

    omega = 2 * np.pi * freq
    n = len(freq)
    dt = 1 / (FS * substeps)
    A = np.zeros((2 * n + 3, 2 * n + 3))
    A[:n, n : 2 * n] = np.diag(omega)
    A[n : 2 * n, :n] = -np.diag(omega)
    A[n : 2 * n, n : 2 * n] = -np.diag(0.04 * omega)
    A[n : 2 * n, -3] = -gamma
    A[-3, -2] = 1
    opened = A.copy()
    opened[n : 2 * n, :n] += np.outer(h, h / omega)
    opened[n : 2 * n, -1] = -h * pre / beta
    matrices = (A, opened)
    advance = [expm(dt * matrix) for matrix in matrices]
    idx = np.arange((len(load) - 1) * substeps + 1)
    acc = np.interp(idx / substeps, np.arange(len(load)), load)
    state = np.zeros(len(A))
    state[-1] = 1.0

    def gap(x):
        return float((beta * h / omega) @ x[:n] - pre)

    history = np.zeros((len(idx), n))
    events = []
    is_open = False
    for i in range(1, len(idx)):
        state[-3:-1] = [acc[i - 1], (acc[i] - acc[i - 1]) / dt]
        end = advance[is_open] @ state
        if (gap(end) > 0) != is_open:
            matrix = matrices[is_open]

            def at(t, dynamics=matrix, initial=state):
                return expm(dynamics * t) @ initial

            t = brentq(lambda t: gap(at(t)), 0.0, dt, xtol=1e-14)
            transition = at(t)
            is_open = not is_open
            assert abs(gap(transition)) < 1e-8
            events.append(
                {
                    "time_s": (i - 1) * dt + t,
                    "opens": is_open,
                    "crossing_speed_m_per_s": float(h @ transition[n : 2 * n] / beta),
                }
            )
            end = expm(matrices[is_open] * (dt - t)) @ transition
            assert (gap(end) > 0) == is_open
        state = end
        history[i] = state[:n] / omega
    return history, events


def cycle(history, h, beta, pre, substeps):
    excess = beta * (history @ h) - pre
    change = np.flatnonzero(np.diff(excess > 0)) + 1
    assert len(change) >= 2 and excess[0] < 0

    def time(k):
        weight = -excess[k - 1] / (excess[k] - excess[k - 1])
        return (k - 1 + weight) / (FS * substeps)

    k, l = change[:2]
    peak = k + int(np.argmax(excess[k:l]))
    return {
        "first_release_ms": 1000 * time(k),
        "first_reclosure_ms": 1000 * time(l),
        "peak_opening_um": float(1e6 * excess[peak] / beta**2),
        "peak_time_ms": 1000 * peak / (FS * substeps),
        "switch_count": len(change),
    }, (int(k), int(peak), int(l))


def simulate():
    from snug_shell_drive_sampling import native_startup

    proof = read(BASIS_PROOF)
    path = OUTPUT / "reduction.npz"
    verified(path, proof["basis_sha256"])
    run = {}
    samples = np.arange(577)
    end = samples[-1] / FS
    for axis in "XYZ":
        evidence = read(ROOT / "validation/independent_motion" / (BRANCH + "_motion_" + axis + ".json"))
        assert evidence["basis_rst_sha256"] == proof["modal_rst_sha256"]
        loadfile = ROOT / ".runtime/motion_loads" / (axis + ".txt")
        verified(loadfile, evidence["input_sha256"])
        t, load = np.loadtxt(loadfile, skiprows=1, max_rows=len(samples)).T
        np.testing.assert_allclose(t, samples / FS, atol=5.1e-13, rtol=0)
        i = "XYZ".index(axis)
        spatial = {}
        temporal = {}
        for blocks in range(proof["residual_blocks"] + 1):
            freq, h, gamma, T, (beta, pre) = model_coordinates(path, blocks)
            g = gamma[:, i]
            q, _ = newmark(freq, h, beta, pre, g, load, 4)
            spatial[4 * blocks] = cycle(q, h, beta, pre, 4)[0]
        previous = spatial[4 * (blocks - 1)]
        finest = spatial[4 * blocks]
        assert abs(previous["peak_opening_um"] / finest["peak_opening_um"] - 1) < 0.013
        assert (
            max(abs(previous[key] - finest[key]) for key in ("first_release_ms", "first_reclosure_ms"))
            < 0.0011
        )
        limit = proof["native_modes"]
        matched = g.copy()
        matched[limit:] = 0
        q_full, events = exact_response(freq, h, beta, pre, g, load, 4)
        result, stations = cycle(q_full, h, beta, pre, 4)
        np.testing.assert_allclose(
            [v["time_s"] * 1000 for v in events[:2]],
            [result["first_release_ms"], result["first_reclosure_ms"]],
            atol=0.0002,
        )
        for subdivisions in (1, 2, 4, 8):
            q, energy = newmark(freq, h, beta, pre, g, load, subdivisions)
            stats, _ = cycle(q, h, beta, pre, subdivisions)
            temporal[subdivisions] = dict(
                **stats,
                work_energy_relative_error=energy,
                relative_force_history_norm=float(
                    np.linalg.norm((q[::subdivisions] - q_full[::4]) @ h)
                    / np.linalg.norm(q_full[::4] @ h)
                ),
            )
        # A second exponential pass changes only the event-search interval.
        _, ev_half = exact_response(freq, h, beta, pre, g, load, 2)
        assert [v["opens"] for v in events] == [v["opens"] for v in ev_half]
        exact_change = max(abs(a["time_s"] - b["time_s"]) for a, b in zip(events, ev_half, strict=True))
        assert exact_change < 1e-9 and temporal[8]["work_energy_relative_error"] < 1e-3
        assert temporal[8]["relative_force_history_norm"] < 0.005
        q_same, ev_same = exact_response(freq, h, beta, pre, matched, load, 4)
        cr, _ = cycle(q_same, h, beta, pre, 4)
        frozen, _, _, _, _ = model_coordinates(path, 0)
        native, identity = native_startup(evidence, CAMPAIGN, frozen, samples)
        # Verify the complete still-seated input and the first crossing at native sampling.
        reference_open = read(AUDIT / (BRANCH + "_pocket_unloading.json"))["axes"][axis]["integrations"][
            "native"
        ]["first_crossing"]["sample"]
        first = np.flatnonzero(beta * (q_same[::4] @ h) > pre)[0]
        assert first == reference_open
        before = samples < first
        baseline_error = np.linalg.norm(q_same[::4, :limit][before] - native[before]) / np.linalg.norm(
            native[before]
        )
        ref_nm, _ = newmark(freq, h, beta, pre, matched, load, 1)
        native_error = np.linalg.norm(ref_nm[before, :limit] - native[before]) / np.linalg.norm(
            native[before]
        )
        assert native_error < 1e-4
        selected = np.array(stations)
        history = OUTPUT / f"{axis}_response.npz"
        np.savez(
            history,
            time_s=np.arange(len(q_full)) / (4 * FS),
            opening_increment_N=beta * (q_full @ h),
            native_frozen_time_s=samples / FS,
            native_frozen_increment_N=beta * (native @ h[:limit]),
            matched_opening_increment_N=beta * (q_same @ h),
            selected=selected,
            selected_q=q_full[selected, :limit],
            selected_residual=q_full[selected, limit:] @ T.T,
            preload_N=pre,
        )
        run[axis] = {
            "input_sha256": evidence["input_sha256"],
            "native_coordinate_source": identity,
            "history_sha256": digest(history),
            "first_cycle": result,
            "exact_state_transitions": events,
            "contact_enrichment": spatial,
            "time_refinement": temporal,
            "matched_native_forcing_first_cycle": cr,
            "max_exact_event_time_change_s": exact_change,
            "preopening_native_Newmark_coordinate_difference": native_error,
            "preopening_exact_vs_native_coordinate_difference": float(baseline_error),
            "selected_stations": selected.tolist(),
            "matched_native_forcing_first_events": ev_same[:2],
        }
        print(axis, result, "matched", cr, "convergence", temporal[8], flush=True)
    write_json(
        STUDY,
        {
            "branch": BRANCH,
            "basis_audit_sha256": digest(BASIS_PROOF),
            "record_duration_s": end,
            "sample_frequency_Hz": FS,
            "axes": run,
            "preload_source": "Independent solid stress recovery at bolt lock",
            "scope": "One unilateral frictionless spring followed during the startup ramp at the original installed geometry. Other contact "
            "states are fixed. Negative trial compression releases the spring, positive compression restores it. Seated modes use "
            "2% damping in both states. The contact law gives spring opening and re-engagement; geometric checks locate other potential contacts.",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "simulate"))
    if parser.parse_args().action == "prepare":
        prepare()
    else:
        simulate()

"""Check the four compression-only spacer seats on the snug board at bolt lock and vibration startup."""

import argparse
import re
import subprocess
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from basis_comparison import field_files
from case_stress import source
from dpf_readback import export
from film_cell_timestep import refined_coordinates
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from scipy.sparse import csc_matrix, triu
from scipy.sparse.linalg import LinearOperator, eigsh
from screw_vibration import screw_elements, section
from seeded_motion import FS, integrate, participation
from snug_board_pull import AUDIT, CAMPAIGN, ROOT, mass_weights, positions, read
from snug_board_tangent import TangentSolver, cell_forces, symmetric_product
from snug_pocket_load_path import element_matrices
from snug_shell_drive_sampling import native_startup

PILOTS = np.arange(950001, 950009)
BRANCHES = ("snug125_nylon", "snug125_aluminium", "snug125_nylon_mesh15")


def seat_stiffness(text):
    assert "KEYOPT,854,4,1" in text
    slopes = []
    for tag in range(870, 874):
        (force,) = re.findall(r"(?im)^R," + str(tag) + r",-\.004,([^,]+),0,0,\.004,0$", text)
        slopes.append(float(force) / -0.004)
    return np.asarray(slopes)


def springs(branch):
    case = branch + "_basis"
    proof, folder, modal = source(case, CAMPAIGN)
    stat, static, raw = source(branch + "_static", CAMPAIGN)
    ledger = read(ROOT / ".runtime/receipts" / CAMPAIGN / case / "archived.json")
    hashes = {r["name"]: r["sha256"] for r in ledger["files"]}
    reg = read(AUDIT / (branch + "_full_board_tangent.json"))
    assert (
        proof["rst_sha256"] == reg["basis_rst_sha256"] and stat["rst_sha256"] == reg["static_rst_sha256"]
    )
    stamp = read(ROOT / ".runtime/receipts" / CAMPAIGN / stat["case"] / "archived.json")
    sha = {r["name"]: r["sha256"] for r in stamp["files"]}
    deck = static / "model.inp"
    verified(deck, sha["model.inp"])
    text = deck.read_text()
    stiffness = seat_stiffness(text)
    area = np.pi * float(re.search(r"(?im)^SECTYPE,851,BEAM,CSOLID\s+SECDATA,([^,]+)", text)[1]) ** 2
    e = float(re.search(r"(?im)^MP,EX,851,([^\r\n]*)", text)[1])
    x0 = raw.mesh.nodes[positions(raw.mesh.nnum, PILOTS)].reshape(4, 2, 3)
    original = np.linalg.norm(x0[:, 1] - x0[:, 0], axis=1)
    np.testing.assert_allclose(original, 0.0076, rtol=1e-9)
    sets = list(range(1, raw.nsets + 1))
    export_dir = export(stat["case"], CAMPAIGN, sets)
    edof = displacement_basis(raw, PILOTS, {i: export_dir / f"set_{i:04d}" for i in sets})
    x = x0 + edof.reshape(raw.nsets, 4, 2, 3)
    v = x[:, :, 1] - x[:, :, 0]
    length = np.linalg.norm(v, axis=-1)
    gap = length - original
    n = v[-1] / length[-1, :, None]
    installed = modal.mesh.nodes[positions(modal.mesh.nnum, PILOTS)].reshape(4, 2, 3)
    np.testing.assert_allclose(x[-1], installed, rtol=0, atol=1e-11)
    g = modal.grid.cell_data
    els = np.sort(g["ansys_elem_num"][g["ansys_etype"] == 854])
    order = np.argsort(modal.mesh.enum)
    np.testing.assert_equal(
        [modal.mesh.elem[i][10:12] for i in order[positions(modal.mesh.enum[order], els)]],
        PILOTS.reshape(4, 2),
    )
    pad_force = stiffness * np.minimum(0, gap[-1])
    tensor = np.zeros((4, 3, 3))
    recovered = np.zeros(4)
    errors = []
    for element, code, keys, mat in element_matrices(folder, els, hashes):
        j = positions(els, [element])[0]
        np.testing.assert_array_equal(keys, (8 * PILOTS[2 * j : 2 * j + 2, None] + np.arange(3)).ravel())
        if code != 0:
            assert np.max(abs(mat)) < 1e-10
            continue
        tensor[j] = mat[3:, 3:]
        np.testing.assert_allclose(
            mat, np.block([[tensor[j], -tensor[j]], [-tensor[j], tensor[j]]]), atol=1e-7
        )
        eig = np.linalg.eigvalsh(tensor[j])
        recovered[j] = np.mean(eig[:2]) * length[-1, j]
        expect = np.array([pad_force[j] / length[-1, j]] * 2 + [stiffness[j] if gap[-1, j] < 0 else 0.0])
        err = float(abs(eig - expect).max())
        assert err < stiffness[j] * 1e-6 and abs(recovered[j] - pad_force[j]) < 1e-6, (
            j,
            err,
            recovered[j],
            pad_force[j],
        )
        errors.append(err)
    assert len(errors) == 4
    _, beam_pos = screw_elements(raw)
    direct = section(raw, raw.nsets - 1, beam_pos, "ENS")[:, :, 0].mean(1) * area
    balance_path = AUDIT / (branch + "_locked_pocket_equilibrium.json")
    balance = read(balance_path)
    rings = np.einsum("ij,ij->i", balance["signed_tab_reactions_on_PLA_XYZ_N"], n)
    # Compare an independent integration across the PLA bearing with the two parallel members.
    error = rings - (direct + pad_force)
    assert np.max(abs(error)) < 0.004, (rings, direct, pad_force)
    record = {
        "branch": branch,
        "static_rst_sha256": stat["rst_sha256"],
        "modal_rst_sha256": proof["rst_sha256"],
        "deck_sha256": sha["model.inp"],
        "tab_force_audit_sha256": digest(balance_path),
        "emat_sha256": {k: h for k, h in hashes.items() if k.endswith(".emat")},
        "seat_elements": els.tolist(),
        "unstrained_grip_m": original.tolist(),
        "seat_stiffness_N_per_m": stiffness.tolist(),
        "beam_stiffness_N_per_m": (e * area / original).tolist(),
        "history": [
            {"set": i + 1, "time": float(t), "signed_seat_extension_nm": (gap[i] * 1e9).tolist()}
            for i, t in enumerate(raw.time_values)
        ],
        "bearing_direction_at_lock": n.tolist(),
        "locked_seat_force_N": pad_force.tolist(),
        "locked_force_from_transverse_tangent_N": recovered.tolist(),
        "max_tangent_error_N_per_m": max(errors),
        "beam_direct_force_N": direct.tolist(),
        "PLA_ring_projected_force_N": rings.tolist(),
        "independent_ring_balance_error_N": error.tolist(),
    }
    return record, proof, folder, modal, hashes, original, v[-1]


def crossings(q, delta, v, original, frequency, cutoff=4000):
    use = frequency <= cutoff
    vdelta = np.tensordot(q[:, use], delta[use], axes=(1, 0))
    length = np.linalg.norm(v, axis=1)
    n = v / length[:, None]
    exact = np.linalg.norm(v[None] + vdelta, axis=2) - original
    linear = length - original + np.einsum("tsd,sd->ts", vdelta, n)
    seats = []
    for j in range(4):
        per = {}
        for method, values in [("current_length", exact[:, j]), ("projected_increment", linear[:, j])]:
            changed = np.flatnonzero((values < 0) != (values[0] < 0))
            if not len(changed):
                per[method] = None
                continue
            i = int(changed[0])
            frac = -values[i - 1] / (values[i] - values[i - 1])
            per[method] = {
                "sample": i,
                "time_bracket_ms": [(i - 1) / FS * 1000, i / FS * 1000],
                "interpolated_ms": (i - 1 + frac) / FS * 1000,
                "transition": "opens" if values[0] < 0 else "closes",
            }
        seats.append(per)
    return seats


def startup(branch, data):
    record, proof, folder, modal, hashes, original, v = data
    shapes = displacement_basis(
        modal, PILOTS, field_files(proof["case"], CAMPAIGN, proof["rst_sha256"], modal.nsets)
    )
    delta = np.diff(shapes.reshape(modal.nsets, 4, 2, 3), axis=2)[:, :, 0]
    verified(folder / "solve.out", hashes["solve.out"])
    samples = np.arange(round(0.04 * FS) + 1)
    axes = {}
    for ax in "XYZ":
        motion = read(ROOT / "validation/independent_motion" / (branch + "_motion_" + ax + ".json"))
        assert (
            motion["basis_rst_sha256"] == proof["rst_sha256"]
            and motion["modal_listing_sha256"] == hashes["solve.out"]
        )
        file = ROOT / ".runtime/motion_loads" / (ax + ".txt")
        verified(file, motion["input_sha256"])
        tt, load = np.loadtxt(file, skiprows=1, max_rows=len(samples)).T
        np.testing.assert_allclose(tt, samples / FS, atol=5.1e-13, rtol=0)
        gamma = participation((folder / "solve.out").read_text(errors="replace"), ax)
        exact, _ = refined_coordinates("linear_input_exact", load, samples, modal.time_values, gamma)
        _, newmark, _ = integrate(modal.time_values, gamma, ax, samples)
        coords = {"exact_linear_input": exact, "Newmark": newmark}
        evidence = {}
        if (ROOT / "validation/motion" / f"{branch}_motion_{ax}.json").is_file():
            coords["native"], evidence = native_startup(motion, CAMPAIGN, modal.time_values, samples)
        histories = {m: crossings(q, delta, v, original, modal.time_values) for m, q in coords.items()}
        method = "native" if "native" in coords else "exact_linear_input"
        cuts = {
            int(c): crossings(coords[method], delta, v, original, modal.time_values, c)
            for c in (3000, 3500)
        }
        axes[ax] = {
            "input_sha256": motion["input_sha256"],
            "coordinate_source": evidence,
            "integrations": histories,
            "truncated_basis": cuts,
        }
    record.update(
        axes=axes,
        sample_frequency_Hz=FS,
        samples=len(samples),
        scope="Compression-only axial seats at the four tied case tabs. Static geometry is checked against native element "
        "stiffness and PLA ring forces. Crossings use the installed modal tangent and the signed distance of the "
        "two seat pilots. Only the first contact change can be interpreted without updating the assembly tangent.",
    )
    write_json(AUDIT / (branch + "_spacer_bearing.json"), record)


def takeup_path(gap, ks, kb, C):
    """Solve the four piecewise-linear seat laws for a common shortening of the free screw lengths."""
    installed = gap < 0
    pieces = []
    # Enumerate the 16 linear branches over a small interval beyond the first complete seating.
    for state in product((False, True), repeat=4):
        active = np.array(state)
        diff = ks * (active.astype(float) - installed)
        matrix = np.eye(4) + C * diff
        a = np.linalg.solve(matrix, -C @ (diff * gap))
        b = np.linalg.solve(matrix, -C @ kb)
        lo, hi = 0.0, np.inf
        for offset, slope, loaded in zip(gap + a, b, active, strict=True):
            sign = -1 if loaded else 1
            intercept = sign * offset
            rate = sign * slope
            if rate > 0:
                lo = max(lo, -intercept / rate)
            elif rate < 0:
                hi = min(hi, -intercept / rate)
            elif intercept < 0:
                hi = -1
        if hi > lo:
            pieces.append((lo, hi, active, a, b))
    pieces.sort(key=lambda v: v[0])
    assert pieces and pieces[0][0] == 0.0 and np.array_equal(pieces[0][2], installed)
    out = []
    for j, (lo, hi, active, a, b) in enumerate(pieces):
        if j:
            prev = pieces[j - 1]
            assert abs(lo - prev[1]) < 1e-11 and np.allclose(
                a + b * lo, prev[3] + prev[4] * lo, atol=1e-11, rtol=0
            )
        delta = a + b * lo
        current = gap + delta
        bearing = ks * np.minimum(0, current)
        correction = bearing - ks * np.minimum(0, gap) - installed * ks * delta
        drive = kb * lo + correction
        np.testing.assert_allclose(delta, -C @ drive, atol=2e-13, rtol=1e-7)
        out.append(
            {
                "free_shortening_nm": float(lo * 1e9),
                "seats_compressed_just_above": [int(i + 1) for i in np.flatnonzero(active)],
                "signed_gap_nm": (1e9 * current).tolist(),
                "seat_compression_N": (-bearing).tolist(),
                "screw_tension_change_N": (kb * (lo + delta)).tolist(),
                "equivalent_tangent_load_N": drive.tolist(),
            }
        )
        if active.all():
            break
    assert sum(pieces[len(out) - 1][2]) == 4
    return out


def bearing_stiffness(branch, data):
    from dmp_board_matrix import assemble
    from snug_pocket_load_path import force_operators, sections

    record, proof, folder, modal, hashes, _, _ = data
    d, free, _, _, G, K, M, identity = assemble(folder, hashes)
    saved = read(AUDIT / (branch + "_spacer_bearing.json"))
    assert all(saved[k] == v for k, v in record.items())
    reference = read(AUDIT / (branch + "_full_board_tangent.json"))
    assert identity == reference["matrix_assembly"]
    keys = 8 * d[:, 0].astype(np.int64) + d[:, 1]
    order = np.argsort(keys)
    n = np.asarray(record["bearing_direction_at_lock"])
    gap = np.array(record["history"][-1]["signed_seat_extension_nm"]) * 1e-9
    ks = np.array(record["seat_stiffness_N_per_m"])
    kb = np.array(record["beam_stiffness_N_per_m"])
    idx = order[positions(keys[order], 8 * PILOTS[:, None] + np.arange(3))].reshape(4, 2, 3)
    cols = np.broadcast_to(np.arange(4)[:, None, None], idx.shape)
    values = np.stack((-n, n), axis=1)
    B0 = csc_matrix((values.ravel(), (idx.ravel(), cols.ravel())), shape=(len(d), 4))
    B = (B0 + G.T @ B0)[free].tocsc()
    ids, w, _ = mass_weights(branch)
    _, cell = cell_forces(d, free, G, ids, w)
    mass = (M + triu(M, 1).T).tocsr()
    active = gap < 0
    src = Path(__file__).with_name("board_tangent_factor.c")
    with TemporaryDirectory() as tmp:
        library = Path(tmp) / "factor.dylib"
        subprocess.run(
            ["clang", "-O2", "-dynamiclib", "-framework", "Accelerate", str(src), "-o", str(library)],
            check=True,
        )
        solver = TangentSolver(K, library)
        try:
            loads = np.column_stack((B.toarray(), cell))
            u = solver.solve(loads)
            Y = u[:, :4]
            C = B.T @ Y
            assert abs(C - C.T).max() < 1e-14 and np.linalg.eigvalsh(C).min() > 0
            initial_residual = np.linalg.norm(symmetric_product(K, u) - loads, axis=0)
            assert initial_residual.max() < 2e-7
            takeup = takeup_path(gap, ks, kb, C)
            states = {}
            for label, mask in [
                ("installed", active),
                ("all_open", np.zeros(4, bool)),
                ("all_bearing", np.ones(4, bool)),
            ]:
                change = (mask.astype(float) - active) * ks
                correction = np.linalg.solve(np.eye(4) + change[:, None] * C, np.diag(change))

                def new_product(x, change=change):
                    return symmetric_product(K, x) + B @ (change[:, None] * (B.T @ x))

                def inverse(rhs, correction=correction):
                    base = solver.solve(rhs)
                    return base - Y @ (correction @ (B.T @ base))

                static = u[:, 4:] - Y @ (correction @ (B.T @ u[:, 4:]))
                residual = np.linalg.norm(new_product(static) - cell, axis=0)
                compliance = 1e6 * cell.T @ static
                assert residual.max() < 2e-7 and abs(compliance - compliance.T).max() < 1e-7
                if label == "installed":
                    np.testing.assert_allclose(compliance, reference["cell_X_um_per_N"], atol=1e-7)
                op = LinearOperator(K.shape, matvec=lambda b: new_product(b[:, None])[:, 0], dtype=float)
                invop = LinearOperator(K.shape, matvec=lambda b: inverse(b[:, None])[:, 0], dtype=float)
                vals, vec = eigsh(
                    op,
                    k=4,
                    M=mass,
                    sigma=0.0,
                    OPinv=invop,
                    ncv=15,
                    tol=2e-9,
                    v0=np.random.default_rng(479).normal(size=len(free)),
                )
                weighted = mass @ vec
                freq = np.sqrt(vals) / (2 * np.pi)
                r = np.linalg.norm(new_product(vec) - weighted * vals, axis=0) / np.linalg.norm(
                    weighted * vals, axis=0
                )
                assert r.max() < 2e-6
                assert abs(vec.T @ weighted - np.eye(4)).max() < 1e-7
                if label == "installed":
                    np.testing.assert_allclose(freq, modal.time_values[:4], rtol=2e-5)
                    original_modes = vec.copy()
                mac = (original_modes.T @ weighted) ** 2
                states[label] = {
                    "first_frequencies_Hz": freq.tolist(),
                    "native_rank_change_Hz": (freq - modal.time_values[:4]).tolist(),
                    "cell_X_um_per_N": compliance.tolist(),
                    "installed_first_four_MAC": mac.tolist(),
                    "modal_equation_relative_residual": r.tolist(),
                    "cell_static_equation_residual": residual.tolist(),
                }
                print(branch, label, freq, flush=True)
            assert np.all(
                np.array(states["all_open"]["first_frequencies_Hz"]) <= modal.time_values[:4] * 1.00002
            )
            assert np.all(
                np.array(states["all_bearing"]["first_frequencies_Hz"])
                >= modal.time_values[:4] * 0.99998
            )
            # Recover the change on the already loaded pocket along the take-up path.
            deck = ROOT / ".runtime/archive" / CAMPAIGN / (branch + "_static") / "model.inp"
            regions, _, _ = sections(branch, modal, deck.read_text())
            port_keys, ops, _ = force_operators(folder, regions, hashes)
            ix = order[positions(keys[order], port_keys)]
            full = np.zeros((len(d), 4))
            full[free] = Y
            full += G @ full
            response = ops["PLA pocket"][0] @ full[ix]
            pocket_file = AUDIT / (branch + "_pocket_unloading.json")
            pocket = read(pocket_file)
            direction = np.array(pocket["opening_direction"])
            pre = pocket["projected_compression_N"][pocket["selected_preload_source"]]
            for row in takeup:
                row["middle_pocket_projected_compression_N"] = float(
                    pre + direction @ response @ row["equivalent_tangent_load_N"]
                )
        finally:
            solver.close()
    write_json(
        AUDIT / (branch + "_spacer_sensitivity.json"),
        {
            "branch": branch,
            "basis_rst_sha256": proof["rst_sha256"],
            "bearing_audit_sha256": digest(AUDIT / (branch + "_spacer_bearing.json")),
            "full_tangent_sha256": digest(AUDIT / (branch + "_full_board_tangent.json")),
            "pocket_force_source_sha256": digest(pocket_file),
            "relative_separation_compliance_m_per_N": C.tolist(),
            "equal_screw_shortening": takeup,
            "conditional_support_states": states,
            "initial_equation_residual": initial_residual.tolist(),
            "scope": "Independent small-displacement calculation on the installed assembly. The stiffness comparisons vary only the four axial "
            "spacer slopes; geometric stiffness, bolt and pocket tangents, mesh and mass stay at the locked state. "
            "The shortening calculation varies the stress-free lengths of the four elastic shanks identically. "
            "It is a sensitivity about the installed state with the pocket tangent fixed; no actual assembly torque or preload was supplied.",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branch", choices=BRANCHES)
    parser.add_argument("--stiffness", action="store_true")
    args = parser.parse_args()
    data = springs(args.branch)
    if args.stiffness:
        bearing_stiffness(args.branch, data)
    else:
        startup(args.branch, data)

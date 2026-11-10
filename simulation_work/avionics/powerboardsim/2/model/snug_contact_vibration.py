"""Integrate seeded board vibration with unilateral pocket and spacer springs at bolt lock."""

import argparse
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from case_stress import source
from dmp_board_matrix import assemble
from early_cell_clearance import outer_faces
from film_identity import digest, verified, write_json
from scipy.linalg import eigh
from scipy.sparse import triu
from seeded_motion import participation
from snug_board_flexibility import equation_modes
from snug_board_pull import AUDIT, BODIES, CAMPAIGN, ROOT, mass_weights, positions, read
from snug_board_tangent import TangentSolver
from snug_pocket_dynamics import residual_basis
from snug_tab_pocket_pull import contact_columns, contacts

BRANCHES = ("snug125_nylon", "snug125_aluminium", "snug125_nylon_mesh15")
CACHE = ROOT / ".runtime/post" / CAMPAIGN


def coordinates(data, blocks):
    n = len(data["frequency"])
    extra = int(data["block_width"]) * blocks
    values, rotation = eigh(data["extra_K"][:extra, :extra])
    assert (values > 0).all()
    omega = np.r_[2 * np.pi * data["frequency"], np.sqrt(values)]

    def rotate(a):
        return np.vstack((a[:n], rotation.T @ a[n : n + extra]))

    return omega, rotate(data["ports"]), rotate(data["drive"]), rotation


def prepare(branch, blocks, centres_only=False):
    stamp = AUDIT / (branch + "_spacer_pocket_pull.json")
    static = read(stamp)
    faces_file = AUDIT / (branch + "_pocket_face_unloading.json")
    verified(faces_file, static["face_preload_sha256"])
    seats_file = AUDIT / (branch + "_spacer_bearing.json")
    verified(seats_file, static["seat_preload_sha256"])
    modal, folder, raw = source(branch + "_basis", CAMPAIGN)
    assert modal["rst_sha256"] == static["modal_rst_sha256"]
    hashes = {
        r["name"]: r["sha256"]
        for r in read(ROOT / ".runtime/receipts" / CAMPAIGN / modal["case"] / "archived.json")["files"]
    }
    parts, k, g, _ = contacts(folder, hashes, read(faces_file), read(seats_file))
    labels = [name for _, _, name in parts]
    assert labels == static["contact_labels"]
    np.testing.assert_allclose(k, static["compression_slope_N_per_m"], rtol=1e-12)
    np.testing.assert_allclose(1e6 * g, static["initial_compression_um"], rtol=1e-12)
    d, free, _, _, transfer, K, M, identity = assemble(folder, hashes)
    assert identity["files"] == static["full_files"]
    B = contact_columns(d, free, transfer, parts)
    mass = (M + triu(M, 1).T).tocsr()
    drive = mass @ (d[free, 1, None] == np.arange(3)).astype(float)
    loads = np.column_stack((B.toarray(), drive))
    n = raw.nsets
    width = loads.shape[1]
    basis = np.empty((len(free), n + blocks * width), order="F")
    for j, mode in enumerate(equation_modes(branch, modal, folder, raw, d, range(n))):
        basis[:, j] = mode[free]
    verified(folder / "solve.out", hashes["solve.out"])
    listing = (folder / "solve.out").read_text(errors="replace")
    gamma = np.column_stack([participation(listing, axis) for axis in "XYZ"])
    direct = basis[:, :n].T @ drive
    projection = np.linalg.norm(direct - gamma, axis=0) / np.linalg.norm(gamma, axis=0)
    assert projection.max() < 4e-5, projection
    with TemporaryDirectory() as tmp:
        lib = Path(tmp) / "factor.dylib"
        subprocess.run(
            [
                "clang",
                "-O2",
                "-dynamiclib",
                "-framework",
                "Accelerate",
                str(Path(__file__).with_name("board_tangent_factor.c")),
                "-o",
                str(lib),
            ],
            check=True,
        )
        solver = TangentSolver(K, lib)
        try:
            extra_K, cross, work, mass_error = residual_basis(basis, mass, K, loads, solver, n, blocks)
        finally:
            solver.close()
    cross_error = float(
        abs(cross / (2 * np.pi * raw.time_values[:, None] * np.sqrt(np.diag(extra_K)))).max()
    )
    assert cross_error < 2e-6
    data = {
        "frequency": raw.time_values,
        "extra_K": extra_K,
        "ports": (B.T @ basis).T,
        "drive": np.vstack((gamma, basis[:, n:].T @ drive)),
        "k": k,
        "g": g,
        "block_width": width,
        "labels": labels,
    }
    arrays = [outer_faces(raw, [m]) for m in (850, *BODIES)]
    ids = np.unique(np.concatenate([faces.ravel() for faces in arrays]))
    columns = 8 * d[:, 0].astype(np.int64) + d[:, 1]
    order = np.argsort(columns)
    take = order[positions(columns[order], 8 * ids[:, None] + np.arange(3))]
    data.update(
        nodes=ids,
        positions=raw.mesh.nodes[positions(raw.mesh.nnum, ids)],
        skin=np.empty((len(ids), 3, basis.shape[1])),
    )
    data.update(
        {
            name: positions(ids, faces)
            for name, faces in zip(("case", "left", "middle", "right"), arrays, strict=True)
        }
    )
    cell_nodes, cell_weights, cell_proof = mass_weights(branch)
    cell_rows = order[positions(columns[order], 8 * cell_nodes[:, None] + np.arange(3))]
    cell_shape = np.empty((3, 3, basis.shape[1]))
    for a in range(0, basis.shape[1], 8):
        size = min(8, basis.shape[1] - a)
        full = np.zeros((len(d), size))
        full[free] = basis[:, a : a + size]
        full += transfer @ full
        data["skin"][:, :, a : a + size] = full[take]
        cell_shape[:, :, a : a + size] = np.einsum("bn,ncj->bcj", cell_weights, full[cell_rows])
    proofs = []
    released = read(AUDIT / f"{branch}_released_pocket_tangent.json")
    spacer = read(AUDIT / f"{branch}_spacer_sensitivity.json")
    initial = g > 0
    for b in range(blocks + 1):
        omega, h, _, _ = coordinates(data, b)
        reduced = (h / omega[:, None]).T @ (h / omega[:, None])
        scaled = (reduced - work[:-3, :-3]) / np.sqrt(np.outer(np.diag(work)[:-3], np.diag(work)[:-3]))
        error = float(abs(scaled).max())
        if b:
            assert error < 5e-6, (b, error)
        controls = {}
        for name, delta, ref in (
            (
                "pocket_open",
                np.r_[-k[:-4], np.zeros(4)],
                [v["open_Hz"] for v in released["first_six_open_modes"][:4]],
            ),
            (
                "spacers_open",
                np.r_[np.zeros(len(k) - 4), -k[-4:] * initial[-4:]],
                spacer["conditional_support_states"]["all_open"]["first_frequencies_Hz"],
            ),
            (
                "spacers_bearing",
                np.r_[np.zeros(len(k) - 4), k[-4:] * (~initial[-4:])],
                spacer["conditional_support_states"]["all_bearing"]["first_frequencies_Hz"],
            ),
        ):
            freq = np.sqrt(
                eigh(np.diag(omega**2) + (h * delta) @ h.T, subset_by_index=[0, 3], eigvals_only=True)
            ) / (2 * np.pi)
            err = float(max(abs(freq - ref)))
            controls[name] = err
            if b >= 2:
                assert err < 0.07, (b, name, err)
        proofs.append(
            {
                "blocks": b,
                "scaled_compliance_matrix_max_error": error,
                "first_four_frequency_max_errors_Hz": controls,
            }
        )
    folder = CACHE / modal["case"] / f"coupled_contact_b{blocks}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "basis.npz"
    record = AUDIT / f"{branch}_contact_vibration_basis.json"
    if centres_only:
        verified(path, read(record)["basis_sha256"])
        with np.load(path) as old:
            for name, val in data.items():
                baseline = old[name]
                if name in (
                    "labels",
                    "nodes",
                    "case",
                    "middle",
                    "left",
                    "right",
                    "block_width",
                    "frequency",
                    "positions",
                    "k",
                    "g",
                ):
                    np.testing.assert_array_equal(val, baseline)
                else:
                    # Each independently rebuilt physical column must represent the same vector.
                    array = np.asarray(val).reshape(-1, val.shape[-1])
                    prev = baseline.reshape(array.shape)
                    errors = np.linalg.norm(array - prev, axis=0) / np.maximum(
                        np.linalg.norm(prev, axis=0), 1e-30
                    )
                    assert errors.max() < 3e-7, (name, errors.max())
    else:
        np.savez(path, **data)
    fs = CACHE / modal["case"] / "cell_mass_mean.npz"
    verified(fs, cell_proof["mean_shapes_sha256"])
    with np.load(fs) as old:
        rows = [np.flatnonzero(old["materials"] == m).item() for m in BODIES]
        np.testing.assert_allclose(cell_shape[:, :, :n], old["mean"][rows], atol=2e-11, rtol=1e-8)
    cp = folder / "cell_centres.npz"
    np.savez(cp, mean=cell_shape)
    write_json(
        AUDIT / f"{branch}_contact_vibration_centres.json",
        {
            "branch": branch,
            "basis_sha256": digest(path),
            "native_modal_rst_sha256": modal["rst_sha256"],
            "mass_weights_sha256": cell_proof["mass_weights_sha256"],
            "native_mean_shapes_sha256": cell_proof["mean_shapes_sha256"],
            "centre_shapes_sha256": digest(cp),
        },
    )
    if centres_only:
        return
    write_json(
        AUDIT / f"{branch}_contact_vibration_basis.json",
        {
            "branch": branch,
            "modal_rst_sha256": modal["rst_sha256"],
            "static_contact_check_sha256": digest(stamp),
            "modal_listing_sha256": hashes["solve.out"],
            "basis_sha256": digest(path),
            "modal_mass_orthogonality_error": mass_error,
            "normalized_cross_stiffness": cross_error,
            "relative_base_participation_error": projection.tolist(),
            "native_modes": n,
            "columns_per_block": width,
            "residual_blocks": blocks,
            "controls": proofs,
        },
    )
    print(branch, "checked and saved", proofs[-1], flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("branch", choices=BRANCHES)
    p.add_argument("--blocks", type=int, default=5)
    p.add_argument(
        "--centres-only",
        action="store_true",
        help="Recover new output on an existing verified reduction",
    )
    opt = p.parse_args()
    prepare(opt.branch, opt.blocks, opt.centres_only)

"""Allow the installed pocket contact points and four spacer seats to change under cell load."""

import argparse
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from case_stress import source
from dmp_board_matrix import assemble
from early_cell_clearance import bezier, outer_faces, subdivision_weights
from film_identity import digest, write_json
from scipy.sparse import csc_matrix
from snug_board_pull import AUDIT, BODIES, CAMPAIGN, ROOT, mass_weights, positions, read
from snug_board_tangent import TangentSolver, cell_forces, symmetric_product
from snug_pocket_faces import at_integration_points
from snug_pocket_load_path import element_matrices
from snug_pocket_release import certify_pair
from snug_spacer_bearing import PILOTS


def contacts(folder, hashes, faces, seats):
    points = faces["integration_points"]
    elements = np.array(faces["elements"])
    six = np.array(faces["face_nodes"])
    parts, stiffness, gap = [], [], []
    reconstruction = {}
    for elem, code, keys, block in element_matrices(folder, elements, hashes, nonzero_only=True):
        assert code == 0
        labels, inv = np.unique(keys, return_inverse=True)
        matrix = np.zeros((len(labels), len(labels)))
        np.add.at(matrix, (inv[:, None], inv[None, :]), block)
        nodes = six[positions(elements, [elem])[0]]
        face_rows = positions(labels, 8 * nodes[:, None] + np.arange(3))
        operators, _ = at_integration_points(matrix[face_rows])
        remade = np.zeros_like(matrix)
        for item in (r for r in points if r["element"] == int(elem)):
            normal = np.array(item["normal"])
            signed = normal @ operators[item["point"] - 1]
            k = float(np.sum(signed[face_rows] * normal))
            assert k > 0
            remade += np.outer(signed, signed) / k
            parts.append((labels, signed / k, f"{elem}.{item['point']}"))
            stiffness.append(k)
            gap.append(item["compression_N"] / k)
        error = float(np.linalg.norm(matrix - remade) / np.linalg.norm(matrix))
        assert error < 2e-6, (elem, error)
        reconstruction[int(elem)] = error
    for j, (i, k0) in enumerate(
        zip(seats["bearing_direction_at_lock"], seats["seat_stiffness_N_per_m"], strict=True)
    ):
        ids = PILOTS.reshape(4, 2)[j]
        parts.append(
            (
                (8 * ids[:, None] + np.arange(3)).ravel(),
                np.concatenate((i, -np.array(i))),
                f"spacer {j + 1}",
            )
        )
        stiffness.append(k0)
        gap.append(-seats["history"][-1]["signed_seat_extension_nm"][j] * 1e-9)
    return parts, np.array(stiffness), np.array(gap), reconstruction


def segments(C, slope, k, g, endpoint):
    """Follow the equilibrium branch exactly between successive changes in bearing."""
    initial = g > 0
    active = initial.copy()
    start = 0.0
    out = []
    for _ in range(64):
        diff = k * (active.astype(float) - initial)
        offset = diff * g
        interval = np.eye(len(g)) + C * diff
        intercept = np.linalg.solve(interval, -C @ offset)
        rate = np.linalg.solve(interval, slope)
        gap0 = g + intercept
        candidates = np.full(len(g), np.inf)
        moving = np.where(active, rate < 0, rate > 0)
        np.divide(-gap0, rate, where=moving, out=candidates)
        candidates[candidates <= start + 1e-10] = np.inf
        stop = min(float(min(candidates)), endpoint)
        midpoint = g + intercept + rate * ((start + stop) / 2)
        assert min(np.where(active, midpoint, -midpoint)) >= -1e-14
        out.append((start, stop, active.copy(), diff, offset, intercept, rate))
        if stop == endpoint:
            return out
        change = abs(candidates - stop) < 1e-9
        active[change] = ~active[change]
        start = stop
    raise RuntimeError("Unresolved bearing transition sequence")


def endpoint_geometry(raw, dofs, free, transfer, displacement, surfaces):
    expanded = np.zeros(len(dofs))
    expanded[free] = displacement
    expanded += transfer @ expanded
    labels = 8 * dofs[:, 0].astype(np.int64) + dofs[:, 1]
    order = np.argsort(labels)
    patches = []
    for surface in surfaces:
        nodes, lookup = np.unique(surface, return_inverse=True)
        xyz = raw.mesh.nodes[positions(raw.mesh.nnum, nodes)]
        dx = expanded[order[positions(labels[order], 8 * nodes[:, None] + np.arange(3))]]
        patches.append(bezier((1000 * (xyz + dx))[lookup.reshape(surface.shape)]))
    return {
        name: certify_pair(patches[0], cell, subdivision_weights())
        for name, cell in zip(("left", "middle", "right"), patches[1:], strict=True)
    }


def contact_columns(d, free, transfer, parts):
    keys = 8 * d[:, 0].astype(np.int64) + d[:, 1]
    order = np.argsort(keys)
    labels = np.concatenate([a for a, _, _ in parts])
    rows = order[positions(keys[order], labels)]
    cols = np.repeat(np.arange(len(parts)), [len(a) for a, _, _ in parts])
    B0 = csc_matrix((np.concatenate([b for _, b, _ in parts]), (rows, cols)), shape=(len(d), len(parts)))
    return (B0 + transfer.T @ B0)[free].tocsc()


def study(branch):
    faces_file = AUDIT / f"{branch}_pocket_face_unloading.json"
    seats_file = AUDIT / f"{branch}_spacer_bearing.json"
    faces, seats = read(faces_file), read(seats_file)
    modal, folder, raw = source(branch + "_basis", CAMPAIGN)
    assert faces["modal_rst_sha256"] == seats["modal_rst_sha256"] == modal["rst_sha256"]
    hashes = {
        r["name"]: r["sha256"]
        for r in read(ROOT / ".runtime/receipts" / CAMPAIGN / modal["case"] / "archived.json")["files"]
    }
    parts, k, g, reconstruction = contacts(folder, hashes, faces, seats)
    d, free, _, _, transfer, K, _, identity = assemble(folder, hashes)
    reference = read(AUDIT / f"{branch}_full_board_tangent.json")
    assert reference["matrix_assembly"] == identity
    B = contact_columns(d, free, transfer, parts)
    ids, w, _ = mass_weights(branch)
    _, cell = cell_forces(d, free, transfer, ids, w)
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
        factor = TangentSolver(K, lib)
        loads = np.column_stack((B.toarray(), cell))
        try:
            u = factor.solve(loads)
        finally:
            factor.close()
    np.testing.assert_allclose(
        cell.T @ u[:, -3:] * 1e6, reference["cell_X_um_per_N"], atol=1e-7, rtol=1e-7
    )
    Y = u[:, : len(g)]
    C = B.T @ Y
    dload = B.T @ u[:, -3:]
    assert abs(C - C.T).max() < 1e-13 and np.linalg.eigvalsh(C).min() > 0
    ru = symmetric_product(K, u) - loads
    assert np.linalg.norm(ru, axis=0).max() < 2e-7
    ids = [label for _, _, label in parts]
    paths = {}
    surfaces = [outer_faces(raw, [material]) for material in (850, *BODIES)]
    # The native board-load controls use +X on the left cell. Negative X on the
    # middle cell unloads its pocket and gives a second, differently directed check.
    for name, j, sign in (("left_plus_X", 0, 1), ("middle_minus_X", 1, -1)):
        path = segments(C, sign * dload[:, j], k, g, 8.54205)
        rows = []
        for lo, hi, mask, diff, offset, intercept, rate in path:
            for t in sorted({lo, hi} | {x for x in (1.0,) if lo < x < hi}):
                advance = intercept + rate * t
                delta = offset + diff * advance
                f = k * np.maximum(0, g + advance)
                np.testing.assert_allclose(
                    delta, f - k * np.maximum(0, g) - k * (g > 0) * advance, atol=1e-7, rtol=1e-7
                )
                disp = sign * t * u[:, -3 + j] - Y @ delta
                np.testing.assert_allclose(B.T @ disp, advance, atol=1e-13, rtol=1e-7)
                # Unreduced equilibrium, including the switched contact loads.
                residual = np.linalg.norm(sign * t * ru[:, -3 + j] - ru[:, : len(k)] @ delta)
                assert residual < 3e-6
                state = {
                    "applied_magnitude_N": t,
                    "cell_X_um": (cell.T @ disp * 1e6).tolist(),
                    "projected_compression_N": f.tolist(),
                    "signed_spring_compression_um": (1e6 * (g + advance)).tolist(),
                    "residual_N": float(residual),
                }
                if rows and abs(rows[-1]["applied_magnitude_N"] - t) < 1e-11:
                    np.testing.assert_allclose(rows[-1]["projected_compression_N"], f, atol=1e-7)
                else:
                    rows.append(state)
        geometry = endpoint_geometry(raw, d, free, transfer, disp, surfaces)
        assert all(s["state"] in ("intersecting", "separated") for s in geometry.values())
        paths[name] = {
            "states": rows,
            "endpoint_quadratic_surfaces": geometry,
            "intervals": [
                {"start_N": a, "end_N": b, "bearing": [ids[i] for i in np.flatnonzero(m)]}
                for a, b, m, *_ in path
            ],
        }
    write_json(
        AUDIT / f"{branch}_spacer_pocket_pull.json",
        {
            "branch": branch,
            "modal_rst_sha256": modal["rst_sha256"],
            "face_preload_sha256": digest(faces_file),
            "seat_preload_sha256": digest(seats_file),
            "full_files": identity["files"],
            "contact_labels": ids,
            "compression_slope_N_per_m": k.tolist(),
            "initial_compression_um": (1e6 * g).tolist(),
            "per_element_relative_stiffness_reconstruction": reconstruction,
            "unit_load_max_residual_N": float(np.linalg.norm(ru, axis=0).max()),
            "paths": paths,
            "scope": "Independent quasi-static response on the installed tangent with the original loaded pocket integration points and four spacer seats free to open or close. Other faces cannot acquire new contact in this calculation. All other geometric stiffnesses, screw ties and original bolt locks are retained.",
        },
    )
    print(
        branch,
        {
            n: [(round(a["start_N"], 5), len(a["bearing"])) for a in q["intervals"]]
            for n, q in paths.items()
        },
        flush=True,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("branch", choices=("snug125_nylon", "snug125_nylon_mesh15", "snug125_aluminium"))
    study(p.parse_args().branch)

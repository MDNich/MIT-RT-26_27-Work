"""Compare seated and open middle-pocket tangents on the same installed board."""

import argparse
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from case_stress import source
from dmp_board_matrix import assemble
from early_cell_clearance import bezier, outer_faces, subdivision_weights, unresolved
from film_cell_contact import (
    TOL_MM,
    candidate_pairs,
    plane_control,
    separate_convex_hulls,
    series,
)
from film_identity import digest, write_json
from installed_cell_gap import target_connectivity
from scipy.linalg import eigh
from scipy.sparse import coo_matrix, triu
from scipy.sparse.linalg import LinearOperator, eigsh
from snug_board_flexibility import equation_modes
from snug_board_pull import (
    AUDIT,
    BODIES,
    CAMPAIGN,
    REGISTRY,
    ROOT,
    mass_weights,
    positions,
    read,
)
from snug_board_tangent import TangentSolver, cell_forces, symmetric_product
from snug_outer_witness import confirm
from snug_pocket_geometry import face_key
from snug_pocket_load_path import element_matrices
from vtkmodules.vtkCommonDataModel import vtkTriangle


def contact_block(folder, rst, hashes, active):
    grid = rst.grid.cell_data
    elements = grid["ansys_elem_num"][grid["ansys_etype"] == 853]
    blocks = {}
    for number, kind, keys, block in element_matrices(folder, elements, hashes, nonzero_only=True):
        # Only the elastic stiffness is nonzero for these frictionless faces.
        assert kind == 0 and number not in blocks and np.all(keys % 8 < 3)
        unique, index = np.unique(keys, return_inverse=True)
        assembled = np.zeros((len(unique), len(unique)))
        np.add.at(assembled, (index[:, None], index[None, :]), block)
        blocks[number] = (unique, assembled)
    assert set(blocks) == set(active)
    keys = np.unique(np.concatenate([k for k, _ in blocks.values()]))
    matrix = np.zeros((len(keys), len(keys)))
    for labels, block in blocks.values():
        at = positions(keys, labels)
        matrix[np.ix_(at, at)] += block
    values, vectors = eigh(matrix)
    tolerance = values[-1] * 1e-12
    assert values[-1] > 0 and values[0] > -tolerance
    keep = values > tolerance
    factors = vectors[:, keep] * np.sqrt(values[keep])
    assert np.linalg.norm(factors @ factors.T - matrix) < 1e-11 * np.linalg.norm(matrix)
    return keys, matrix, factors, len(elements), values[keep]


def frequencies(branch, basis, folder, rst, dofs, free, opened, mass, solver):
    """Recover the first six open modes and compare their shapes with the native installed basis."""
    diag = opened.diagonal()
    operator = LinearOperator(
        opened.shape, dtype=float, matvec=lambda x: opened @ x + opened.T @ x - diag * x
    )
    inverse = LinearOperator(
        opened.shape, dtype=float, matvec=lambda x: solver.solve(x.reshape(-1, 1))[:, 0]
    )
    lambdas, shapes = eigsh(
        operator,
        k=6,
        M=mass,
        OPinv=inverse,
        sigma=0,
        tol=1e-9,
        ncv=18,
        v0=np.random.default_rng(731).normal(size=len(free)),
    )
    freq = np.sqrt(lambdas) / (2 * np.pi)
    weighted = mass @ shapes
    residual = np.linalg.norm(
        symmetric_product(opened, shapes) - weighted * lambdas, axis=0
    ) / np.linalg.norm(weighted * lambdas, axis=0)
    orthogonality = float(abs(shapes.T @ weighted - np.eye(len(freq))).max())
    assert residual.max() < 1e-6 and orthogonality < 1e-7
    assert (freq > 0).all() and (freq <= rst.time_values[: len(freq)] * (1 + 1e-7)).all()
    # All retained native eigenvectors are mass-normalized in this coordinate system.
    # A score is a shape match, so it need not pair equal mode numbers.
    correlations = []
    for mode in equation_modes(branch, basis, folder, rst, dofs, range(rst.nsets)):
        correlations.append(mode[free] @ weighted)
    mac = np.square(correlations).T
    assert mac.sum(1).max() < 1.0001
    rows = []
    for i, frequency in enumerate(freq):
        j = int(np.argmax(mac[i]))
        rows.append(
            {
                "open_rank": i + 1,
                "open_Hz": float(frequency),
                "seated_same_rank_Hz": float(rst.time_values[i]),
                "closest_seated_rank": j + 1,
                "closest_seated_Hz": float(rst.time_values[j]),
                "mass_MAC": float(mac[i, j]),
                "mass_MAC_by_native_rank": mac[i].tolist(),
                "generalized_residual": float(residual[i]),
            }
        )
    return rows, orthogonality


def single_contact_path(
    dofs, free, transfer, seated, opened, open_stiffness, load, contact_eq, factors, Hcap, check, endpoint
):
    """Follow a single compression-only linear spring through unloading at fixed contact normal."""
    assert factors.shape[1] == 1
    preload = check["projected_compression_N"][check["selected_preload_source"]]
    direction = np.array(check["opening_direction"])
    slope = np.array(check["opening_force_increment_N_per_unit_positive_X_load"])
    b = float((-direction @ Hcap).item())
    assert abs(abs(b) / np.linalg.norm(Hcap) - 1) < 1e-4
    paths = []
    fields = []
    for j, force in [(0, 0.0), (0, 1.0), (0, preload / slope[0]), (0, endpoint), (1, -1.0)]:
        opening = slope[j] * force
        switch = preload / slope[j]
        if opening > preload:
            u = seated[:, j] * switch + opened[:, j] * (force - switch)
        else:
            u = seated[:, j] * force
        opening_trial = float((b * factors.T @ u[contact_eq]).item())
        pressure = max(0.0, preload - opening_trial)
        separation = max(0.0, opening_trial - preload) / (abs(b) * np.linalg.norm(Hcap))
        assert abs(pressure - max(0.0, preload - opening)) < 1e-8
        delta = min(opening_trial, preload) / b
        residual = symmetric_product(open_stiffness, u[:, None])[:, 0] - load[:, j] * force
        residual[contact_eq] += factors[:, 0] * delta
        equilibrium_error = float(np.linalg.norm(residual))
        assert equilibrium_error < 1e-7
        state = np.zeros((len(dofs), 1))
        state[free, 0] = u
        state += transfer @ state
        fields.append(state[:, 0])
        paths.append(
            {
                "loaded_cell": ("left", "middle", "right")[j],
                "applied_X_N": force,
                "predicted_cell_centres_X_um": (1e6 * load.T @ u).tolist(),
                "held_closed_cell_centres_X_um": (1e6 * (load.T @ seated[:, j]) * force).tolist(),
                "remaining_compression_N": pressure,
                "spring_opening_past_zero_um": 1e6 * separation,
                "independent_equation_residual_N": equilibrium_error,
            }
        )
    return paths, np.stack(fields)


def certify_pair(a, b, weights):
    """Require a curved-patch witness or separation of all surviving Bernstein hull pairs."""
    ia, ib = candidate_pairs(
        (a.min(1) - TOL_MM, a.max(1) + TOL_MM), (b.min(1) - TOL_MM, b.max(1) + TOL_MM)
    )
    x, y = a[ia], b[ib]
    counts = []
    for depth in range(13):
        keep = unresolved(x, y, TOL_MM)
        x, y, ia, ib = (data[keep] for data in (x, y, ia, ib))
        if len(x):
            keep = separate_convex_hulls(x, y)
            x, y, ia, ib = (data[keep] for data in (x, y, ia, ib))
        counts.append(len(x))
        if not len(x):
            return {"state": "separated", "surviving_pairs": counts}
        if depth >= 3:
            tested = set()
            for i, (child_a, child_b) in enumerate(zip(x, y, strict=True)):
                pair = (ia[i], ib[i])
                if pair in tested or not vtkTriangle.TrianglesIntersect(*child_a[:3], *child_b[:3]):
                    continue
                tested.add(pair)
                witness = confirm(a[[pair[0]]], b[[pair[1]]])
                if witness is not None:
                    witness.update(PLA_face=int(pair[0]), cell_face=int(pair[1]))
                    return {"state": "intersecting", "surviving_pairs": counts, "witness": witness}
        if depth == 12 or len(x) > 50000:
            break
        x = np.repeat(weights @ x[:, None], 4, axis=1).reshape(-1, 6, 3)
        y = np.tile(weights @ y[:, None], (1, 4, 1, 1)).reshape(-1, 6, 3)
        ia = np.repeat(ia, 16)
        ib = np.repeat(ib, 16)
    return {"state": "unresolved", "surviving_pairs": counts}


def witness_elements(rst, pla_face, cell_face):
    contact = face_key(pla_face)
    target = face_key(cell_face)
    grid = rst.grid.cell_data
    numbers = grid["ansys_elem_num"][grid["ansys_etype"] == 853]
    order = np.argsort(rst.mesh.enum)
    indices = order[positions(rst.mesh.enum[order], numbers)]
    elements = rst.mesh.elem
    (case_id,) = [
        int(number)
        for number, i in zip(numbers, indices, strict=True)
        if face_key(elements[i][10:18][[0, 1, 2, 4, 5, 7]]) == contact
    ]
    (target_id,) = [
        int(number)
        for number, face in target_connectivity(rst).items()
        if face[2] == face[3] and face_key(np.array(face)[[0, 1, 2, 4, 5, 7]]) == target
    ]
    return {"case_contact_element": case_id, "cell_target_element": target_id}


def check_surfaces(rst, dofs, fields, records, paths):
    """Test the curved skins at the piecewise path's saved states, including the prior active face."""
    surfaces = [outer_faces(rst, [material]) for material in (850, *BODIES)]
    (active_row,) = records
    order = np.argsort(rst.mesh.enum)
    native = rst.mesh.elem[order[positions(rst.mesh.enum[order], [active_row])[0]]]
    surfaces.append(native[10:18][[0, 1, 2, 4, 5, 7]][None, :])
    ids = np.unique(np.concatenate([f.ravel() for f in surfaces]))
    keys = 8 * dofs[:, 0].astype(np.int64) + dofs[:, 1]
    sort = np.argsort(keys)
    displacement = 1000 * fields[:, sort[positions(keys[sort], ids[:, None] * 8 + np.arange(3))]]
    xyz = 1000 * rst.mesh.nodes[positions(rst.mesh.nnum, ids)]
    idx = [positions(ids, face) for face in surfaces]
    rest = [bezier(xyz[f]) for f in idx]
    modes = [bezier(displacement[:, f]) for f in idx]
    weights = subdivision_weights()
    plane_control(weights)
    states = {}
    for first, last, label in [
        (0, 1, "left"),
        (0, 2, "middle"),
        (0, 3, "right"),
        (4, 2, "original_face_to_middle"),
    ]:
        state, pairs, levels = series(
            [rest[first], rest[last]], [modes[first], modes[last]], np.eye(len(fields)), weights
        )
        states[label] = {
            "classifications": state,
            "candidate_pairs": pairs,
            "intersection_refinements": levels,
        }

    # A coarse triangulation may cross at two levels while the exact skins are
    # disjoint. A witness on the previously active face also proves a crossing
    # for the full shell, avoiding a second search over the same patch.
    def middle_state(i, j, fraction):
        def moved(side):
            return rest[side] + (1 - fraction) * modes[side][i] + fraction * modes[side][j]

        cell = moved(2)
        contact = certify_pair(moved(4), cell, weights)
        if contact["state"] == "intersecting":
            whole = {"state": "intersecting", "confirmed_on_original_face": True}
        else:
            whole = certify_pair(moved(0), cell, weights)
        return contact, whole

    checks = [middle_state(i, i, 0.0) for i in range(len(fields))]
    states["original_face_to_middle"]["curved_checks"] = [c for c, _ in checks]
    states["middle"]["curved_checks"] = [w for _, w in checks]
    lo, hi = 2, 3
    assert paths[lo]["loaded_cell"] == paths[hi]["loaded_cell"] == "left"
    if checks[lo][1]["state"] == "intersecting" and checks[hi][1]["state"] == "separated":
        lower, upper = 0.0, 1.0
        a, b = paths[lo]["applied_X_N"], paths[hi]["applied_X_N"]
        stations = []
        while (upper - lower) * (b - a) > 0.05:
            fraction = (lower + upper) / 2
            original, whole = middle_state(lo, hi, fraction)
            stations.append(
                {"applied_X_N": a + fraction * (b - a), "original_face": original, "whole_shell": whole}
            )
            if whole["state"] == "unresolved":
                break
            if whole["state"] == "intersecting":
                lower = fraction
            else:
                upper = fraction
        states["middle_surface_transition"] = {
            "intersecting_X_N": a + lower * (b - a),
            "separated_X_N": a + upper * (b - a),
            "tests": stations,
            "scope": "Opposite certified surface states along the open linear branch. No monotonicity assumption.",
        }
        for station in stations:
            whole = station["whole_shell"]
            if "witness" in whole:
                witness = whole["witness"]
                witness.update(
                    witness_elements(
                        rst, surfaces[0][witness["PLA_face"]], surfaces[2][witness["cell_face"]]
                    )
                )
    states["interpretation"] = (
        "The initial classifications use triangulated crossings. The curved_checks require an exact interior crossing or disjoint enclosing hulls. Use the latter where both are present."
    )
    return states


def compare(branch, matrices, library):
    full_path = AUDIT / f"{branch}_full_board_tangent.json"
    prior = read(full_path)
    load_path = AUDIT / f"{branch}_initial_cell_load_paths.json"
    recovery = read(load_path)
    assert recovery["full_tangent_sha256"] == digest(full_path)
    basis, folder, rst = source(branch + "_basis", CAMPAIGN)
    assert basis["rst_sha256"] == prior["basis_rst_sha256"] == recovery["modal_check"]["rst_sha256"]
    ledger = read(ROOT / ".runtime/receipts" / CAMPAIGN / basis["case"] / "archived.json")
    hashes = {v["name"]: v["sha256"] for v in ledger["files"]}
    keys, block, H, nfaces, positive = contact_block(
        folder, rst, hashes, recovery["installed_contact_elements"]
    )
    d, free, fixed, _, G, K, M, identity = matrices
    assert identity == prior["matrix_assembly"]
    allkeys = 8 * d[:, 0].astype(np.int64) + d[:, 1]
    order = np.argsort(allkeys)
    equations = order[positions(allkeys[order], keys)]
    ix = positions(free, equations)
    assert not G[equations].nnz
    row, col = np.triu_indices(len(ix))
    difference = coo_matrix(
        (block[row, col], (np.minimum(ix[row], ix[col]), np.maximum(ix[row], ix[col]))), K.shape
    ).tocsc()
    opened = (K - difference).tocsc()
    ids, weights, mass_proof = mass_weights(branch)
    assert mass_proof["mass_weights_sha256"] == prior["mass_weights_sha256"]
    cell_eq = np.flatnonzero(np.isin(d[free, 0], ids))
    grid = rst.grid.cell_data
    cap_elements = grid["ansys_elem_num"][grid["ansys_etype"] == 850]
    sort = np.argsort(rst.mesh.enum)
    elements = rst.mesh.elem
    cap_nodes = np.unique(
        np.stack([elements[i][10:20] for i in sort[positions(rst.mesh.enum[sort], cap_elements)]])
    )
    cap_eq = np.flatnonzero(np.isin(d[free, 0], cap_nodes))

    def max_coupling(stiffness):
        return max(
            float(abs(stiffness[a][:, b]).max()) for a, b in ((cap_eq, cell_eq), (cell_eq, cap_eq))
        )

    before, after = max_coupling(K), max_coupling(opened)
    assert before > 0 and after < before * 1e-12
    loads, load = cell_forces(d, free, G, ids, weights)
    assert not loads[fixed].any()
    U = np.zeros((len(free), H.shape[1]))
    U[ix] = H
    mass = (M + triu(M, 1).T).tocsr()
    factor = TangentSolver(opened, library)
    try:
        solution = factor.solve(np.column_stack((load, U)))
        open_u, z = solution[:, :3], solution[:, 3:]
        # Restore all removed springs through the Woodbury identity.
        interaction = H.T @ z[ix]
        assert np.allclose(interaction, interaction.T, rtol=1e-8, atol=1e-9)
        closed_u = open_u - z @ np.linalg.solve(np.eye(H.shape[1]) + interaction, H.T @ open_u[ix])
        compliance = 1e6 * load.T @ open_u
        closed = 1e6 * load.T @ closed_u
        np.testing.assert_allclose(closed, prior["cell_X_um_per_N"], atol=1e-8, rtol=1e-8)
        assert abs(compliance - compliance.T).max() < 1e-8
        assert np.linalg.eigvalsh(compliance - closed).min() > -1e-9
        res_open = np.linalg.norm(symmetric_product(opened, open_u) - load, axis=0)
        res_closed = np.linalg.norm(symmetric_product(K, closed_u) - load, axis=0)
        assert max(res_open.max(), res_closed.max()) < 1e-7
        Hcap = np.stack(
            [H[(keys % 8 == axis) & np.isin(keys // 8, cap_nodes)].sum(0) for axis in range(3)]
        )
        forces = -Hcap @ (H.T @ closed_u[ix])
        prior_forces = recovery["element_group_XYZ_N_per_N"]["PLA pocket"]
        assert abs(forces - prior_forces).max() < 1e-8
        modes, orthogonality = frequencies(branch, basis, folder, rst, d, free, opened, mass, factor)
    finally:
        factor.close()
    result = {
        "branch": branch,
        "modal_rst_sha256": basis["rst_sha256"],
        "full_tangent_sha256": digest(full_path),
        "installed_load_paths_sha256": digest(load_path),
        "mass_weights_sha256": prior["mass_weights_sha256"],
        "full_files_sha256": identity["files"],
        "emat_files_sha256": {f"file{i}.emat": hashes[f"file{i}.emat"] for i in range(12)},
        "number_of_case_contact_faces": nfaces,
        "nonzero_contact_elements": recovery["installed_contact_elements"],
        "contact_rank": H.shape[1],
        "positive_contact_eigenvalues_N_per_m": positive.tolist(),
        "maximum_direct_case_cell_stiffness_N_per_m": {"seated": before, "open": after},
        "cell_order": ["left", "middle", "right"],
        "open_compliance_X_um_per_N": compliance.tolist(),
        "restored_compliance_X_um_per_N": closed.tolist(),
        "maximum_restored_pocket_force_difference_N_per_N": float(abs(forces - prior_forces).max()),
        "open_equation_residuals_N": res_open.tolist(),
        "restored_equation_residuals_N": res_closed.tolist(),
        "first_six_open_modes": modes,
        "mass_orthogonality_max_error": orthogonality,
        "scope": "Independent tangent comparison at bolt lock. Opening removes every nonzero cell-to-case contact matrix. "
        "The printed shell, four mounts, original supports, mass and remaining installed tangents stay in the model. "
        "These frequencies describe fixed contact states, not an impact or a time-varying frequency measurement.",
    }
    if H.shape[1] == 1:
        unload_path = AUDIT / f"{branch}_pocket_unloading.json"
        check = read(unload_path)
        assert check["initial_load_paths_sha256"] == digest(load_path)
        nominal = branch.removesuffix("_mesh15")
        end = read(REGISTRY)[nominal + "_cellpush_x"]["endpoint_force_N"]
        paths, fields = single_contact_path(
            d, free, G, closed_u, open_u, opened, load, ix, H, Hcap, check, end
        )
        result["single_contact_prediction"] = {
            "unloading_record_sha256": digest(unload_path),
            "normal_spring_stiffness_N_per_m": float(np.linalg.norm(Hcap) ** 2),
            "preload_to_spring_normal_cosine": float(
                abs((np.array(check["opening_direction"]) @ Hcap).item()) / np.linalg.norm(Hcap)
            ),
            "states": paths,
            "curved_cell_surfaces": check_surfaces(
                rst, d, fields, recovery["installed_contact_elements"], paths
            ),
            "scope": "Piecewise linear, frictionless spring with an initial compression offset. Other contact and material states are held fixed.",
        }
    write_json(AUDIT / f"{branch}_released_pocket_tangent.json", result)
    print(
        branch,
        "compliance",
        np.diag(compliance),
        "rank",
        H.shape[1],
        "first Hz",
        modes[0]["open_Hz"],
        flush=True,
    )


def run(branch):
    folder = ROOT / ".runtime/archive" / CAMPAIGN / (branch + "_basis")
    ledger = read(ROOT / ".runtime/receipts" / CAMPAIGN / folder.name / "archived.json")
    hashes = {r["name"]: r["sha256"] for r in ledger["files"]}
    with TemporaryDirectory() as tmp:
        library = Path(tmp) / "board.dylib"
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
        compare(branch, assemble(folder, hashes), library)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "branch",
        choices=(
            "snug125_aluminium",
            "snug125_nylon",
            "snug125_nylon_mesh15",
            "snug125_aluminium_mesh15",
        ),
    )
    run(parser.parse_args().branch)

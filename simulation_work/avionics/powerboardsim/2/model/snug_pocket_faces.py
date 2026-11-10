"""Resolve the installed middle-pocket reaction by native contact triangle."""

import argparse

import numpy as np
from ansys.mapdl.reader.rst import ELEMENT_INDEX_TABLE_KEYS
from basis_comparison import field_files
from case_stress import source
from film_cell_timestep import refined_coordinates
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from seeded_motion import FS, integrate, participation
from snug_board_pull import AUDIT, CAMPAIGN, ROOT, positions, read
from snug_locked_contact import element_contact_forces
from snug_pocket_load_path import element_matrices
from snug_pocket_preload import normal_controls
from snug_shell_drive_sampling import native_startup

# Quadratic triangle shape functions at its three symmetric integration stations.
BARYCENTRIC = np.eye(3) / 2 + np.full((3, 3), 1 / 6)
SHAPE = np.vstack(
    ((BARYCENTRIC * (2 * BARYCENTRIC - 1)).T, (4 * BARYCENTRIC * np.roll(BARYCENTRIC, -1, axis=1)).T)
)
SIX = [0, 1, 2, 4, 5, 7]


def at_integration_points(nodal):
    """Invert virtual work on the six case nodes and check every reconstructed nodal force."""
    flat = nodal.reshape(6, -1)
    points, _, rank, _ = np.linalg.lstsq(SHAPE, flat, rcond=None)
    residual = float(np.linalg.norm(SHAPE @ points - flat) / np.linalg.norm(flat))
    assert rank == 3 and residual < 3.0e-7, residual
    return points.reshape(3, *nodal.shape[1:]), residual


def inherited_forces(raw, elems):
    """Sum all eight case-side ENF records, including the repeated corner on each degenerate face."""
    order = np.argsort(raw._eeqv)
    rows = order[positions(raw._eeqv[order], elems)]
    index = ELEMENT_INDEX_TABLE_KEYS.index("ENF")
    out = np.empty((len(elems), 6, 3))
    for j in range(raw.nsets):
        indices, _, offset = raw._element_solution_header(j)
        for i, ix in enumerate(rows):
            pointer = int(offset + indices[ix])
            slot = int(raw.read_record(pointer)[index])
            assert indices[ix] > 0 and slot > 0
            force = raw.read_record(pointer + slot)
            assert len(force) == 288 and not np.any(force[96:])
            nodal = force[:96].reshape(32, 3)
            assert np.max(abs(nodal.sum(axis=0, dtype=float))) < 1e-6
            six = nodal[SIX].astype(float)
            six[2] += nodal[[3, 6]].sum(axis=0, dtype=float)
            if j == 0:
                out[i] = six
            else:
                np.testing.assert_array_equal(out[i], six)
    # Public reader independently verifies record selection and the active face set at lock.
    numbers, values, _ = raw.element_solution_data(0, "ENF")
    grid = raw.grid.cell_data
    surfaces = np.sort(grid["ansys_elem_num"][grid["ansys_etype"] == 853])
    resultant = np.zeros((len(surfaces), 3))
    for i, row in enumerate(positions(numbers, surfaces)):
        if values[row] is not None and len(values[row]):
            resultant[i] = values[row][:24].reshape(8, 3).sum(axis=0, dtype=float)
    active = np.any(resultant != 0, axis=1)
    np.testing.assert_array_equal(surfaces[active], elems)
    np.testing.assert_allclose(resultant[active], out.sum(1), atol=1e-14)
    return out


def modal_increments(modal, folder, raw, faces, face_nodes):
    ledger = read(ROOT / ".runtime/receipts" / CAMPAIGN / modal["case"] / "archived.json")
    hashes = {r["name"]: r["sha256"] for r in ledger["files"]}
    fields = field_files(modal["case"], CAMPAIGN, modal["rst_sha256"], raw.nsets)
    rank = {}
    shape_forces = np.empty((len(faces), 6, 3, raw.nsets))
    for elem, code, keys, block in element_matrices(folder, faces, hashes, nonzero_only=True):
        assert code == 0
        i = positions(faces, [elem])[0]
        unique, inverse = np.unique(keys, return_inverse=True)
        assembled = np.zeros((len(unique), len(unique)))
        np.add.at(assembled, (inverse[:, None], inverse[None, :]), block)
        eig = np.linalg.eigvalsh(assembled)
        rank[int(elem)] = int((eig > eig[-1] * 1e-12).sum())
        nodes = np.unique(unique // 8)
        shape = displacement_basis(raw, nodes, fields)
        disp = shape[:, positions(nodes, unique // 8), unique % 8]
        forces = assembled @ disp.T
        shape_forces[i] = forces[positions(unique, 8 * face_nodes[i, :, None] + np.arange(3))]

    assert sorted(rank) == faces.tolist()
    return rank, shape_forces


def crossing(values):
    matches = np.flatnonzero(values <= 0)
    if not len(matches):
        return None
    k = int(matches[0])
    assert k > 0 and values[k - 1] > 0
    f = values[k - 1] / (values[k - 1] - values[k])
    return {"end_sample": k, "interpolated_ms": float((k - 1 + f) * 1000 / FS)}


def run(branch):
    eq_file = AUDIT / f"{branch}_locked_pocket_equilibrium.json"
    net_file = AUDIT / f"{branch}_pocket_unloading.json"
    eq, net = read(eq_file), read(net_file)
    modal, folder, raw = source(branch + "_basis", CAMPAIGN)
    assert modal["rst_sha256"] == net["modal_rst_sha256"] and net["locked_equilibrium_sha256"] == digest(
        eq_file
    )
    faces = np.array(eq["active_elements"])
    assert np.all(np.diff(faces) > 0)
    face_nodes = np.array(eq["active_six_node_faces"])
    assert len(faces) == len(face_nodes)
    static, static_folder, installed = source(eq["static_case"], CAMPAIGN)
    assert static["rst_sha256"] == eq["rst_sha256"]
    source_name = net["selected_preload_source"]
    reaction = np.array(eq["force_into_shell_XYZ_N"][source_name])
    transmitted = inherited_forces(raw, faces)
    locked = -transmitted.sum(axis=1)
    if source_name == "native_contact":
        independent_static = element_contact_forces(installed, eq["native_set"] - 1, faces)
        np.testing.assert_allclose(locked, independent_static, rtol=2e-7, atol=1e-9)
        direct = np.genfromtxt(static_folder / "snug_contact_force.csv", delimiter=",", names=True)
        assert direct[-1]["native_set"] == eq["native_set"]
        np.testing.assert_allclose(
            locked.sum(0), [direct[-1][k] for k in ("fx_N", "fy_N", "fz_N")], atol=2e-7
        )
    else:
        assert len(faces) == 1 and source_name == "PLA_pocket"
        np.testing.assert_allclose(locked.sum(0), -reaction, atol=1e-5)
    preload_difference = float(np.linalg.norm(locked.sum(0) + reaction))
    magnitude = np.linalg.norm(locked, axis=1)
    normals = locked / magnitude[:, None]
    patches = raw.mesh.nodes[positions(raw.mesh.nnum, face_nodes)]
    np.testing.assert_allclose(patches, eq["lock_patch_xyz_m"], atol=1e-10)
    normal_bounds = []
    for normal, patch in zip(normals, patches, strict=True):
        normals_bezier = normal_controls(patch)
        bound = min(normals_bezier @ normal) / max(np.linalg.norm(normals_bezier, axis=1))
        assert bound > 0.90, (normal, bound)
        normal_bounds.append(float(bound))
    ranks, nodal_shapes = modal_increments(modal, folder, raw, faces, face_nodes)
    shape = nodal_shapes.sum(1)
    stations, point_balance = [], []
    for i, e in enumerate(faces):
        base, base_error = at_integration_points(-transmitted[i])
        modal_points, shape_error = at_integration_points(nodal_shapes[i])
        # Two independent classifications: nonzero installed force and nonzero tangent.
        stiff = np.linalg.norm(modal_points, axis=(1, 2))
        loaded = np.linalg.norm(base, axis=1) > np.linalg.norm(base) * 1e-6
        np.testing.assert_array_equal(loaded, stiff > stiff.max() * 1e-8)
        assert np.count_nonzero(loaded) == ranks[int(e)]
        point_balance.append(
            {"element": int(e), "static_relative_error": base_error, "modal_relative_error": shape_error}
        )
        for g in np.flatnonzero(loaded):
            force = np.linalg.norm(base[g])
            direction = base[g] / force
            projected = direction @ modal_points[g]
            off_normal = float(
                np.linalg.norm(modal_points[g] - direction[:, None] * projected) / stiff[g]
            )
            assert off_normal < 3e-4, (e, g, off_normal)
            assert min(normal_controls(patches[i]) @ direction) > 0
            stations.append(
                {
                    "element": int(e),
                    "point": int(g + 1),
                    "XYZ_mm": (1000 * SHAPE[:, g] @ patches[i]).tolist(),
                    "compression_N": float(force),
                    "normal": direction.tolist(),
                    "modal_off_normal_fraction": off_normal,
                    "projected_shapes": projected,
                }
            )
    point_shapes = np.stack([x.pop("projected_shapes") for x in stations], axis=1)
    point_preloads = [x["compression_N"] for x in stations]
    cache = ROOT / ".runtime/post" / CAMPAIGN / modal["case"] / "attachment_modes.npz"
    verified(cache, net["modal_force_shapes_sha256"])
    with np.load(cache) as f:
        whole = f["middle_cell_pocket_force"]
    net_err = np.linalg.norm(shape.sum(0) + whole) / np.linalg.norm(whole)
    assert net_err < 2e-6, net_err
    compression = np.einsum("ijk,ij->ki", shape, normals)
    load_path = read(AUDIT / f"{branch}_initial_cell_load_paths.json")
    static_slopes = np.stack(
        [
            normals[i] @ load_path["element_group_XYZ_N_per_N"][f"contact {e}"]
            for i, e in enumerate(faces)
        ]
    )
    samples = np.arange(round(0.04 * FS) + 1)
    axes = {}
    for axis in "XYZ":
        motion_file = ROOT / "validation/independent_motion" / (branch + "_motion_" + axis + ".json")
        motion = read(motion_file)
        assert digest(motion_file) == net["axes"][axis]["independent_motion_sha256"]
        loads = ROOT / ".runtime/motion_loads" / (axis + ".txt")
        verified(loads, motion["input_sha256"])
        listing = folder / "solve.out"
        verified(listing, motion["modal_listing_sha256"])
        gamma = participation(listing.read_text(errors="replace"), axis)
        t, acc = np.loadtxt(loads, skiprows=1, max_rows=len(samples)).T
        np.testing.assert_allclose(t, samples / FS, atol=5.1e-13, rtol=0)
        exact, _ = refined_coordinates("linear_input_exact", acc, samples, raw.time_values, gamma)
        _, newmark, _ = integrate(raw.time_values, gamma, axis, samples)
        q = {"exact_linear_input": exact, "Newmark": newmark}
        if net["axes"][axis]["native_coordinate_source"]:
            q["native"], identity = native_startup(motion, CAMPAIGN, raw.time_values, samples)
            assert identity == net["axes"][axis]["native_coordinate_source"]
        selected = "native" if "native" in q else "exact_linear_input"
        responses = {}
        for method, coordinates in q.items():
            for hz in [3000, 3500, 4000] if method == selected else [4000]:
                keep = raw.time_values <= hz
                face_force = magnitude + coordinates[:, keep] @ compression[keep]
                all_faces = [crossing(v) for v in face_force.T]
                first, i = min(
                    (c["interpolated_ms"], i) for i, c in enumerate(all_faces) if c is not None
                )
                total_axis = -np.array(net["opening_direction"])
                projected = np.linalg.norm(reaction) + coordinates[:, keep] @ (
                    total_axis @ whole[:, keep]
                )
                net_cross = crossing(projected)
                assert (
                    net_cross["end_sample"]
                    == net["axes"][axis]["integrations"][method]["crossing_sample_by_cutoff_Hz"][str(hz)]
                )
                all_points = [
                    crossing(v) for v in (point_preloads + coordinates[:, keep] @ point_shapes[keep]).T
                ]
                pt_first, j = min(
                    (c["interpolated_ms"], j) for j, c in enumerate(all_points) if c is not None
                )
                assert pt_first <= first + 1e-4
                k = all_faces[i]["end_sample"]
                responses[f"{method}_{hz}"] = {
                    "first_face_ms": first,
                    "first_element": int(faces[i]),
                    "each_face": all_faces,
                    "pocket_projection_at_first_face_N": float(projected[k]),
                    "net_crossing": net_cross,
                    "each_point": all_points,
                    "first_point_ms": pt_first,
                    "first_point": [stations[j]["element"], stations[j]["point"]],
                    "net_compression_at_first_point_N": float(projected[all_points[j]["end_sample"]]),
                }
        chosen = responses[f"{selected}_4000"]
        for control in responses.values():
            assert control["first_point"] == chosen["first_point"]
            assert abs(control["first_point_ms"] - chosen["first_point_ms"]) < 1000 / FS
        axes[axis] = {
            "histories": responses,
            "selected": selected + "_4000",
            "input_sha256": motion["input_sha256"],
        }
    record = {
        "branch": branch,
        "modal_rst_sha256": modal["rst_sha256"],
        "static_rst_sha256": eq["rst_sha256"],
        "preload_source": "base contact nodal forces inherited by all perturbation modes",
        "independent_preload_source": source_name,
        "force_vector_difference_from_reference_N": preload_difference,
        "locked_equilibrium_sha256": digest(eq_file),
        "net_audit_sha256": digest(net_file),
        "elements": faces.tolist(),
        "locked_CNF_N": locked.tolist(),
        "compression_N": magnitude.tolist(),
        "face_nodes": face_nodes.tolist(),
        "integration_points": stations,
        "nodal_reconstruction": point_balance,
        "face_centres_m": patches[:, :3, :].mean(1).tolist(),
        "normal_lower_cosines": normal_bounds,
        "tangent_ranks": ranks,
        "net_force_modal_relative_error": net_err,
        "signed_first_tangent_zero_X_load_N_by_left_middle_right": (
            -magnitude[:, None] / static_slopes
        ).tolist(),
        "sample_rate_Hz": FS,
        "axes": axes,
        "scope": "Compression projected along each installed face reaction. Face and integration-point force zeros are extrapolations of the installed tangent. "
        "Initially open contacts and other interfaces can change sooner. For aluminium, an independent solid-stress integral checks the inherited native contact preload.",
    }
    write_json(AUDIT / (branch + "_pocket_face_unloading.json"), record)
    print(
        branch,
        [(k, round(v["histories"][v["selected"]]["first_face_ms"], 3)) for k, v in axes.items()],
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branch", choices=["snug125_nylon", "snug125_nylon_mesh15", "snug125_aluminium"])
    run(parser.parse_args().branch)

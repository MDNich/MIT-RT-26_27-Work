"""Recover the seated pocket reaction from the native solid stresses on each side."""

import argparse

import numpy as np
from case_stress import case_elements, corners, source
from cell_attachment_force import bodies_and_bonds
from dpf_readback import export
from film_identity import digest, verified, write_json
from scipy.spatial.transform import Rotation
from snug_board_pull import AUDIT, CAMPAIGN, ROOT, positions, read
from snug_equilibrium_residual import accepted_substeps
from snug_mount_reactions import ring_nodes
from snug_pocket_preload import normal_controls
from snug_tab_submodel import gradient, quadrature


def solid_nodal_forces(rst, elements, connectivity, ids, xyz, station):
    """Integrate grad(N) times Cauchy stress on the deformed ten-node tetrahedra."""
    nodes, stress = corners(rst, station, "ENS", elements, 6)
    frame_nodes, angles = corners(rst, station, "EUL", elements, 3)
    np.testing.assert_array_equal(nodes, frame_nodes)
    np.testing.assert_array_equal(nodes, ids[connectivity[:, :4]].ravel())
    stress = stress.reshape(-1, 4, 6)
    tensor = np.zeros((*stress.shape[:2], 3, 3))
    tensor[:, :, 0, 0], tensor[:, :, 1, 1], tensor[:, :, 2, 2] = stress[:, :, :3].transpose(2, 0, 1)
    for component, (i, j) in enumerate(((0, 1), (1, 2), (0, 2)), 3):
        tensor[:, :, i, j] = tensor[:, :, j, i] = stress[:, :, component]
    rot = Rotation.from_euler("ZXY", angles, degrees=True).as_matrix().reshape(tensor.shape)
    tensor = rot @ tensor @ rot.transpose(0, 1, 3, 2)
    local = xyz[connectivity] - xyz[connectivity[:, :1]]
    forces = np.zeros_like(local)
    stress_integral = np.zeros((len(elements), 3, 3))
    for gp, weight in quadrature(False):
        deriv = gradient(gp)
        jac = local.transpose(0, 2, 1) @ deriv
        det = np.linalg.det(jac)
        assert np.min(det) > 0
        weighted_stress = np.einsum("i,eijk->ejk", gp, tensor) * (det * weight)[:, None, None]
        forces += deriv @ np.linalg.inv(jac) @ weighted_stress
        stress_integral += weighted_stress
    # Rigid virtual translations and all nine affine virtual displacement fields.
    work = local.transpose(0, 2, 1) @ forces
    balance = float(abs(forces.sum(axis=1)).max())
    work_error = float(abs(work - stress_integral).max())
    assert balance < 1e-10 and work_error < 1e-12, (balance, work_error)
    nodal = np.zeros_like(xyz)
    np.add.at(nodal, connectivity.ravel(), forces.reshape(-1, 3))
    return nodal, {"max_element_force_sum_N": balance, "max_affine_work_error_Nm": work_error}


def recover(branch):
    native_case = branch + ("_out2_static" if branch == "snug125_nylon" else "_static")
    proof, archive, rst = source(native_case, CAMPAIGN)
    source_file = AUDIT / f"{native_case}_contacts.json"
    installed = read(source_file)
    assert installed["rst_sha256"] == proof["rst_sha256"]
    parent = read(AUDIT / f"{branch}_static_contacts.json")
    assert installed["step_sha256"] == parent["step_sha256"]
    assert installed["case_mesh_sha256"] == parent["case_mesh_sha256"]
    assert installed["contact_history"] == parent["contact_history"]
    history = installed["contact_history"]
    assert history[-1]["loadstep"] == 2 and history[-1]["load_time"] == 2 and rst.nsets == len(history)
    global_proof = read(ROOT / ".runtime/receipts" / CAMPAIGN / native_case / "archived.json")
    hashes = {row["name"]: row["sha256"] for row in global_proof["files"]}
    listing = archive / "solve.out"
    verified(listing, hashes[listing.name])
    accepted = accepted_substeps(listing.read_text(errors="replace"))
    assert len(accepted) == rst.nsets
    deck = archive / "model.inp"
    verified(deck, hashes[deck.name])
    rings, _ = ring_nodes(deck.read_text())
    geometry = read(ROOT / "validation/cell_force" / f"{branch}.json")["geometry"]
    bodies, bonds, _ = bodies_and_bonds(rst, geometry)
    cell_elements, cell_ids, cell_conn = bodies[191]
    cell_conn = cell_conn.reshape(-1, 10)
    ends = [ends[0][1] for ends in bonds.values() if ends[0][0] == 191]
    assert len(ends) == 2
    off_bonds = ~np.isin(cell_ids, np.concatenate(ends))
    elements = case_elements(rst, native_case.removesuffix("_static"))
    enum = rst.mesh.enum
    order = np.argsort(enum)
    connectivity = np.stack([rst.mesh.elem[i][10:20] for i in order[positions(enum[order], elements)]])
    ids, conn = np.unique(connectivity, return_inverse=True)
    conn = conn.reshape(connectivity.shape)
    controls = installed.get("resultant_force_check")
    # The final bolt-lock state is the reference for all subsequent force increments.
    k = rst.nsets - 1
    row = history[k]
    (active,) = row["loaded_case_faces"]
    assert active["STEP_face"] == 17
    faces = [rst.mesh.elem[i][10:18] for i in order[positions(enum[order], active["element_ids"])]]
    faces = np.stack(faces)
    np.testing.assert_array_equal(faces[:, 2], faces[:, 3])
    np.testing.assert_array_equal(faces[:, 2], faces[:, 6])
    faces = faces[:, [0, 1, 2, 4, 5, 7]]
    ufile = export(native_case, CAMPAIGN, [k + 1]) / f"set_{k + 1:04d}"
    node = np.fromfile(ufile.with_suffix(".ids"), "<i4")
    displacement = np.fromfile(ufile.with_suffix(".u"), "<f8").reshape(-1, 3)
    sort = np.argsort(node)

    def current(numbers):
        return (
            rst.mesh.nodes[positions(rst.mesh.nnum, numbers)]
            + displacement[sort[positions(node[sort], numbers)]]
        )

    xyz = current(ids)
    forces, shell_work = solid_nodal_forces(rst, elements, conn, ids, xyz, k)
    patch = np.unique(faces)
    pocket = forces[positions(ids, patch)].sum(axis=0)
    tabs = np.stack([forces[positions(ids, ring)].sum(axis=0) for ring in rings.values()])
    free = ~np.isin(ids, np.concatenate([patch, *rings.values()]))
    cell_forces, cell_work = solid_nodal_forces(
        rst, cell_elements, cell_conn, cell_ids, current(cell_ids), k
    )
    cell = cell_forces[off_bonds].sum(axis=0)
    assert np.allclose(cell, -cell_forces[~off_bonds].sum(axis=0), atol=1e-9)
    assert np.allclose(tabs.sum(0) + pocket, -forces[free].sum(0), atol=1e-9)
    direction = -pocket / np.linalg.norm(pocket)
    bounds = []
    for points in xyz[positions(ids, faces)]:
        controls_normal = normal_controls(points)
        bounds.append(
            float((controls_normal @ direction).min() / np.linalg.norm(controls_normal, axis=1).max())
        )
    assert min(bounds) > 0.95
    vectors = {"PLA_pocket": pocket, "four_mounts": -tabs.sum(0), "middle_cell": -cell}
    if controls:
        assert controls[k]["native_set"] == k + 1
        vectors["native_contact"] = -np.array(controls[k]["force_xyz_N"])
    # Every independent measurement must support the choice of force direction.
    align = {key: float(-v @ direction / np.linalg.norm(v)) for key, v in vectors.items()}
    assert min(align.values()) > 0.999
    spread = max(np.linalg.norm(v - pocket) for v in vectors.values())
    assert spread < 0.05 * np.linalg.norm(pocket)
    result = {
        "branch": branch,
        "static_case": native_case,
        "rst_sha256": proof["rst_sha256"],
        "native_set": k + 1,
        "model_sha256": hashes[deck.name],
        "listing_sha256": hashes[listing.name],
        "contact_audit_sha256": digest(source_file),
        "displacement_sha256": digest(ufile.with_suffix(".u")),
        "displacement_ids_sha256": digest(ufile.with_suffix(".ids")),
        "active_elements": active["element_ids"],
        "active_six_node_faces": faces.tolist(),
        "lock_patch_xyz_m": xyz[positions(ids, faces)].tolist(),
        "pocket_node_count": len(patch),
        "original_face_count": len(faces),
        "shell_elements": len(elements),
        "cell_elements": len(cell_elements),
        "force_into_shell_XYZ_N": {key: value.tolist() for key, value in vectors.items()},
        "force_into_shell_norm_N": {key: float(np.linalg.norm(value)) for key, value in vectors.items()},
        "signed_tab_reactions_on_PLA_XYZ_N": tabs.tolist(),
        "projected_directions_cosine": align,
        "max_difference_from_PLA_recovery_N": float(spread),
        "minimum_curved_face_normal_cosine": min(bounds),
        "free_shell_force_L2_N": float(np.linalg.norm(forces[free])),
        "native_final_force_residual_N": accepted[k]["force_residual_N"],
        "shell_virtual_work": shell_work,
        "cell_virtual_work": cell_work,
        "scope": "Independent spatial virtual work from native SOLID187 corner stresses, orientations and nodal displacements at bolt lock. "
        "All resultant vectors use the force transferred from the cell into the PLA. The optional native contact sum reports the opposite side and is sign-reversed.",
    }
    write_json(AUDIT / f"{branch}_locked_pocket_equilibrium.json", result)
    print(branch, result["force_into_shell_norm_N"], "cosine", min(align.values()), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "branch",
        choices=(
            "snug125_nylon",
            "snug125_nylon_mesh15",
            "snug125_aluminium",
            "snug125_aluminium_mesh15",
        ),
    )
    recover(parser.parse_args().branch)

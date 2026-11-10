"""Check the deformed case, cells and washers at the saved whole-board side-load equilibria."""

import argparse
from itertools import product

import numpy as np
from dpf_readback import export
from early_cell_clearance import bezier, outer_faces, subdivision_weights
from film_cell_contact import TOL_MM, candidate_pairs
from film_identity import digest, verified, write_json
from native_rst import read_rst
from snug_board_pull import AUDIT, BODIES, BRANCHES, CAMPAIGN, ROOT, positions, read
from snug_locked_contact import contact_parts
from snug_pocket_release import certify_pair
from snug_pocket_sampling import groups
from snug_prescribed_contact import predicted, stiffness_and_force
from snug_surface_distance import surface_distance
from tab_seating import read_point_file
from vtkmodules.vtkCommonDataModel import vtkQuadraticQuad


def washer_controls(xyz):
    """Tensor-product quadratic Bézier hull of each eight-node serendipity face."""
    if xyz.shape[1] == 6:
        return bezier(xyz)
    assert xyz.shape[1] == 8
    nodes = xyz[:, [0, 4, 1, 7, 0, 5, 3, 6, 2]].reshape(-1, 3, 3, 3).copy()
    nodes[:, 1, 1] = 0.5 * xyz[:, 4:].sum(1) - 0.25 * xyz[:, :4].sum(1)
    transform = np.array([[1, 0, 0], [-0.5, 2, -0.5], [0, 0, 1]])
    ctrl = np.einsum("ij,njkc,lk->nilc", transform, nodes, transform)
    return ctrl.reshape(-1, 9, 3)


def projected_separation(a, b):
    """Lower bound for each pair of Bernstein patches, projected onto unit axes."""
    gap = np.linalg.norm(np.maximum(0, np.maximum(a.min(1) - b.max(1), b.min(1) - a.max(1))), axis=1)
    j, k = (1, 2) if b.shape[1] == 6 else (2, 6)
    directions = (
        np.cross(a[:, 1] - a[:, 0], a[:, 2] - a[:, 0]),
        a.mean(1) - b.mean(1),
        np.cross(b[:, j] - b[:, 0], b[:, k] - b[:, 0]),
    )
    for d in directions:
        d /= np.maximum(np.linalg.norm(d, axis=1)[:, None], 1e-30)
        ap = np.einsum("nij,nj->ni", a - b[:, :1], d)
        bp = np.einsum("nij,nj->ni", b - b[:, :1], d)
        gap = np.maximum(gap, np.maximum(ap.min(1) - bp.max(1), bp.min(1) - ap.max(1)))
    return gap


def children(controls, tri_weights):
    if controls.shape[1] == 6:
        return tri_weights @ controls[:, None]
    half = np.array(
        [[[1, 0, 0], [0.5, 0.5, 0], [0.25, 0.5, 0.25]], [[0.25, 0.5, 0.25], [0, 0.5, 0.5], [0, 0, 1]]]
    )
    return np.einsum("aij,njkc,blk->nabilc", half, controls.reshape(-1, 3, 3, 3), half).reshape(
        -1, 4, 9, 3
    )


def check_washer_shape():
    # Evaluate each independent serendipity shape function on all four child patches.
    xyz = np.zeros((8, 8, 3))
    xyz[:, :, 0] = np.eye(8)
    patches = children(washer_controls(xyz), subdivision_weights()).reshape(8, 2, 2, 3, 3, 3)
    largest = 0.0
    for j, i in product(range(2), repeat=2):
        for v, u in product(np.linspace(0, 1, 5), repeat=2):
            native = [0.0] * 8
            vtkQuadraticQuad.InterpolationFunctions([(i + u) / 2, (j + v) / 2, 0], native)
            bu = [(1 - u) ** 2, 2 * u * (1 - u), u * u]
            bv = [(1 - v) ** 2, 2 * v * (1 - v), v * v]
            recovered = np.einsum("j,k,njk->n", bv, bu, patches[:, j, i, :, :, 0])
            largest = max(largest, float(np.max(np.abs(recovered - native))))
    assert largest < 1e-12
    return largest


def lower_washer_gap(shell, groups, limit, weights):
    """Exclude all patch pairs closer than the reported bound, up to the chosen clearance screen."""
    lower = limit
    for faces in groups:
        bound = washer_controls(faces)
        ia, ib = candidate_pairs(
            (shell.min(1) - limit, shell.max(1) + limit), (bound.min(1), bound.max(1))
        )
        a, b = shell[ia], bound[ib]
        for depth in range(5):
            if not len(a):
                break
            gap = projected_separation(a, b)
            keep = gap < limit + TOL_MM
            if not np.any(keep):
                break
            if depth == 4 or keep.sum() > 4000:
                lower = min(lower, gap.min())
                break
            aa, bb = children(a[keep], weights), children(b[keep], weights)
            a = np.repeat(aa, 4, axis=1).reshape(-1, 6, 3)
            b = np.tile(bb, (1, 4, 1, 1)).reshape(-1, b.shape[1], 3)
    return float(max(0, lower - TOL_MM))


def audit(branch):
    washer_shape_error = check_washer_shape()
    case = branch + "_cellpush_x"
    path = AUDIT / (case + ".json")
    data = read(path)
    assert data["case"] == case
    rst_file = ROOT / ".runtime/archive" / CAMPAIGN / case / "file.rst"
    verified(rst_file, data["rst_sha256"])
    raw = read_rst(rst_file)
    surfaces = [outer_faces(raw, [mat]) for mat in (850, *BODIES)]
    parts, targets = contact_parts(raw)
    washers = {}
    for (number, _), part in zip(targets[3:], parts[4:], strict=True):
        node_ids = part.point_data["ansys_node_num"]
        washers[number] = [node_ids[v] for v in part.cells_dict.values()]
    ids = np.unique(
        np.concatenate(
            [f.ravel() for f in surfaces] + [f.ravel() for w in washers.values() for f in w]
        )
    )
    initial = raw.mesh.nodes[positions(raw.mesh.nnum, ids)] * 1000
    cell_faces = [positions(ids, f) for f in surfaces]
    washer_faces = {n: [positions(ids, f) for f in w] for n, w in washers.items()}
    mesh = {"nodes": raw.mesh.nnum, "middle": positions(raw.mesh.nnum, surfaces[2])}
    (pocket, barrel), parent = groups(branch, mesh)
    assert parent["rst_sha256"] == data["parent_rst_sha256"]
    caps, case_nodes, case0, _, _ = pocket
    targets, cell_nodes, cell0, axis, radius = barrel
    si, ti = (positions(ids, raw.mesh.nnum[v]) for v in (case_nodes, cell_nodes))
    np.testing.assert_allclose(initial[si], case0, atol=1e-7, rtol=0)
    np.testing.assert_allclose(initial[ti], cell0, atol=1e-7, rtol=0)
    sets = [s["native_set"] for s in data["states"]]
    out = ROOT / ".runtime/post" / CAMPAIGN / case / "fit_surfaces"
    u, _ = read_point_file(rst_file, out, data["rst_sha256"], sets, ids.tolist())
    assert data["states"][0]["time"] == 2 and parent["case"] == branch + "_static"
    locked = export(parent["case"], CAMPAIGN, [sets[0]]) / f"set_{sets[0]:04d}"
    parent_ids = np.fromfile(locked.with_suffix(".ids"), "<i4")
    order = np.argsort(parent_ids)
    parent_u = np.fromfile(locked.with_suffix(".u"), "<f8").reshape(-1, 3)
    overlap_error = np.max(np.abs(u[0] - 1000 * parent_u[order[positions(parent_ids[order], ids)]]))
    assert overlap_error < 1e-8, overlap_error
    weights = subdivision_weights()
    rows = []
    for state, dx in zip(data["states"], u, strict=True):
        step = state["native_set"]
        xyz = initial + dx
        shell, *cells = [bezier(xyz[f]) for f in cell_faces]
        geometries = {}
        for label, body in zip(("left", "middle", "right"), cells, strict=True):
            geo = certify_pair(shell, body, weights)
            if geo["state"] == "separated" and state["time"] in (3.0, 5.0, 6.0):
                geo["distance"] = surface_distance(shell, body, tolerance_mm=0.00001)
                if label == "middle":
                    coarse = geo["distance"]
                    fine = surface_distance(shell, body, tolerance_mm=1e-6)
                    assert max(coarse["lower_mm"], fine["lower_mm"]) <= min(
                        coarse["upper_mm"], fine["upper_mm"]
                    )
                    geo["coarse_distance"] = coarse
                    geo["distance"] = fine
            geometries[label] = geo
        lower = {
            n: lower_washer_gap(shell, [xyz[f] for f in patches], 0.32, weights)
            for n, patches in washer_faces.items()
        }
        r = {
            "native_set": step,
            "time": state["time"],
            "applied_X_N": state["applied_X_N"],
            "cells": geometries,
            "washer_clearance_lower_mm": lower,
        }
        if "native_middle_pocket_force" in state:
            kn, native = stiffness_and_force(raw, step - 1, caps)
            force, points, _ = predicted(caps, targets, xyz[si], xyz[ti], cell0, axis, radius, kn)
            native_on_shell = -np.asarray(state["native_middle_pocket_force"]["CNF_XYZ_N"])
            np.testing.assert_allclose(native.sum(0), native_on_shell, rtol=1e-9, atol=1e-9)
            r.update(
                native_loaded_middle_faces=caps[np.linalg.norm(native, axis=1) > 1e-8].tolist(),
                reconstructed_middle_points=points,
                barrel_force_on_shell_N=force.sum(0).tolist(),
                native_force_on_shell_N=native_on_shell.tolist(),
                force_vector_difference_N=float(np.linalg.norm(force.sum(0) - native_on_shell)),
            )
        rows.append(r)
        print(case, step, [g["state"] for g in geometries.values()], min(lower.values()), flush=True)
    write_json(
        AUDIT / (case + "_fit.json"),
        {
            "case": case,
            "native_pull_sha256": digest(path),
            "rst_sha256": data["rst_sha256"],
            "displacement_sha256": digest(out / "displacements.bin"),
            "parent_displacement_sha256": digest(locked.with_suffix(".u")),
            "maximum_parent_overlap_error_mm": float(overlap_error),
            "native_sets": sets,
            "washer_screen_mm": 0.32,
            "max_washer_shape_function_error": washer_shape_error,
            "states": rows,
            "scope": "Independent geometry on native deformed quadratic skins at saved stations. The washer lower bounds use "
            "Bézier convex hulls of all native triangular and serendipity-quadrilateral target faces. "
            "The pressure reconstruction probes the three pocket integration stations against the cylindrical barrel. "
            "Surface intersection between integration points can coincide with zero saved contact pressure. "
            "Clearances apply to the discretized assembly without manufacturing tolerances.",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branches", nargs="+", choices=BRANCHES[1:])
    for branch in parser.parse_args().branches:
        audit(branch)

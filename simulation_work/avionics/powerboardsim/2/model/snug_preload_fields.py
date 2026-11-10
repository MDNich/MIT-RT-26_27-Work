"""Compare native displacement vectors at identical material points in the preload controls."""

import argparse

import numpy as np
from case_stress import source
from dpf_readback import export
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_board_pull import AUDIT, BODIES, CAMPAIGN, ROOT, read
from snug_mesh_comparison import force_pair
from stage_snug_fit import PRELOAD_CONTROLS, input_record


def locked_fields(case):
    proof, _, raw = source(case, CAMPAIGN)
    prefix = export(case, CAMPAIGN, [raw.nsets]) / f"set_{raw.nsets:04d}"
    record = read(ROOT / "validation/static" / (case + ".json"))["models"][case]
    assert record["source_rst_sha256"] == proof["rst_sha256"]
    verified(prefix.with_suffix(".u"), record["native_DPF_U_sha256"])
    verified(prefix.with_suffix(".ids"), record["native_DPF_ID_sha256"])
    ids = np.fromfile(prefix.with_suffix(".ids"), "<i4")
    order = np.argsort(ids)
    u_mm = 1000 * np.fromfile(prefix.with_suffix(".u"), "<f8").reshape(-1, 3)[order]
    assert raw.time_values[-1] == 2
    return raw, ids[order], u_mm, record


def differences(ids, coords, reference_mm, other_mm):
    assert len(ids) > 0 and np.array_equal(reference_mm.shape, other_mm.shape)
    diff = 1000 * (other_mm - reference_mm)
    norms = np.linalg.norm(diff, axis=1)
    maximum = np.argmax(norms)
    return {
        "matched_nodes": len(ids),
        "max_vector_difference_um": float(norms[maximum]),
        "peak_node": int(ids[maximum]),
        "peak_reference_xyz_mm": coords[maximum].tolist(),
        "peak_delta_XYZ_um": diff[maximum].tolist(),
        "rms_nodal_difference_um": float(np.sqrt(np.mean(norms**2))),
        "p95_nodal_difference_um": float(np.quantile(norms, 0.95)),
    }


def audit(case):
    spec = input_record(case)
    same_mesh = "absolute_force_criterion_N" in spec
    material = spec["material"]
    branch = "snug125_" + material
    reference, comparison = force_pair(case)
    old, new = read(comparison)["runs"]
    assert old["case"] == reference and new["case"] == case
    base, ids0, u0, record0 = locked_fields(old["case"])
    control, ids1, u1, record1 = locked_fields(case)
    assert (
        old["rst_sha256"] == record0["source_rst_sha256"]
        and new["rst_sha256"] == record1["source_rst_sha256"]
    )
    sectors = {
        "PCB": [208],
        "cells": BODIES,
        "nickel_strips": [174, 179, 180, 186, 189, 193],
        "washers": [173, 178, 181, 182, 183, 192],
    }
    if same_mesh:
        assert spec["mesh_sha256"] == input_record(old["case"])["mesh_sha256"]
        sectors["printed_case"] = [850]
    domain = {}
    for name, materials in sectors.items():
        pair = []
        for raw in (base, control):
            g = raw.quadgrid
            select = np.isin(g.cell_data["ansys_elem_type_num"], [185, 186, 187]) & np.isin(
                g.cell_data["ansys_material_type"], materials
            )
            pair.append(np.unique(g.extract_cells(select).point_data["ansys_node_num"]))
        ids, check = pair
        np.testing.assert_array_equal(ids, check)
        xyz = base.mesh.nodes[positions(base.mesh.nnum, ids)]
        np.testing.assert_allclose(
            xyz, control.mesh.nodes[positions(control.mesh.nnum, ids)], atol=1e-12, rtol=0
        )
        domain[name] = differences(ids, 1000 * xyz, u0[positions(ids0, ids)], u1[positions(ids1, ids)])
    out = {
        "case": case,
        "reference": old["case"],
        "force_comparison_sha256": digest(comparison),
        "reference_native_U_sha256": record0["native_DPF_U_sha256"],
        "control_native_U_sha256": record1["native_DPF_U_sha256"],
        "reference_rst_sha256": old["rst_sha256"],
        "control_rst_sha256": new["rst_sha256"],
        "solids_at_lock": domain,
        "scope": "Native three-component displacement differences in the fixed PCB coordinates at final bolt lock. "
        "Each pair has the same native node ID and reference position. Nodal summaries use equal node weights.",
    }
    if same_mesh and spec["size_mm"] == 2:
        restart = branch + "_cellpush_x"
        pull = read(AUDIT / (restart + ".json"))
        fitfile = AUDIT / (restart + "_fit.json")
        fit = read(fitfile)
        verified(AUDIT / (restart + ".json"), fit["native_pull_sha256"])
        src = ROOT / ".runtime/post" / CAMPAIGN / restart / "fit_surfaces"
        req = read(src / "request.json")
        done = read(src / "done.json")
        assert req["source_sha256"] == done["source_sha256"] == pull["rst_sha256"] == fit["rst_sha256"]
        assert done["sets"] == req["sets"] == fit["native_sets"]
        file = src / "displacements.bin"
        verified(file, fit["displacement_sha256"])
        ids = np.array(req["nodes"])
        assert len(ids) == len(np.unique(ids)) == done["nodes"]
        forward = (
            np.fromfile(file, "<f8").reshape(len(req["sets"]), len(ids), 3)
            * {"m": 1000.0, "mm": 1.0}[done["unit"].lower()]
        )
        k = [v["time"] for v in pull["states"]].index(3.0)
        old_u = u0[positions(ids0, ids)]
        new_u = u1[positions(ids1, ids)]
        np.testing.assert_allclose(old_u, forward[0], rtol=0, atol=1e-8)
        xyz = 1000 * base.mesh.nodes[positions(base.mesh.nnum, ids)]
        out["comparison_to_original_zero_load_hold"] = {
            "restart_fit_sha256": digest(fitfile),
            "native_set": req["sets"][k],
            "original_lock_vs_strict_lock": differences(ids, xyz, old_u, new_u),
            "original_hold_vs_strict_lock": differences(ids, xyz, forward[k], new_u),
            "original_pressure_N": pull["pocket_unloading_check"]["original_projected_compression_N"],
            "original_hold_pressure_N": pull["pocket_unloading_check"][
                "zero_hold_native_projection_N"
            ],
            "scope": "Case, all three cell surfaces and all six washer surfaces common to the closed side-load restart.",
        }
    write_json(AUDIT / (case + "_matched_fields.json"), out)
    print(case, {name: val["max_vector_difference_um"] for name, val in domain.items()}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "case",
        choices=[
            *PRELOAD_CONTROLS,
            "snug125_nylon_mesh15_static",
            "snug125_aluminium_mesh15_static",
            "snug125_nylon_tol001_static",
        ],
    )
    audit(parser.parse_args().case)

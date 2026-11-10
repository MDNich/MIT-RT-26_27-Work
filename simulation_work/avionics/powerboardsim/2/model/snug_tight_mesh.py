"""Compare nylon case meshes with the same verified 0.01 N force criterion."""

import numpy as np

from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_board_pull import AUDIT, BODIES, ROOT, read
from snug_mesh_comparison import statistics
from snug_preload_fields import differences, locked_fields
from stage_snug_fit import input_record


def compare():
    cases = ("snug125_nylon_tol001_static", "snug125_nylon_mesh15_tol001_static")
    runs, native = [], []
    for case in cases:
        spec = input_record(case)
        assert spec["absolute_force_criterion_N"] == 0.01 and spec["material"] == "nylon"
        run = statistics(case)
        pathfile = AUDIT / (case + "_load_path.json")
        barrelfile = AUDIT / (case + "_barrel_tractions.json")
        residualfile = AUDIT / (case + "_residuals.json")
        path, barrel, residual = map(read, (pathfile, barrelfile, residualfile))
        assert path["rst_sha256"] == barrel["rst_sha256"] == residual["rst_sha256"] == run["rst_sha256"]
        verified(pathfile, barrel["native_and_solid_balance_sha256"])
        rows = []
        for load, surface, solve, time in zip(path["states"], barrel["states"], residual["states"], run["times"], strict=True):
            assert time == load["time"] == surface["time"] == solve["load_time"]
            assert solve["force_criterion_N"] == 0.01 and solve["force_residual_N"] <= 0.01
            assert load["within_existing_bearing_force_screens"] and surface["mounting_force_balance_passed"]
            assert surface["loaded_faces_match"]
            force = float(np.linalg.norm(load["native_contact_resultant_XYZ_N"]))
            np.testing.assert_allclose(force, surface["native_net_N"], atol=1e-9, rtol=1e-9)
            rows.append(dict(time=time, pocket_resultant_N=force,
                bearing_vector_residual_N=load["difference_from_native_contact_N"]["four_tabs"],
                loaded_points=len(surface["points"]), loaded_faces=len(surface["native_faces"]),
                loaded_quadrature_area_mm2=surface["loaded_quadrature_area_mm2"],
                peak_radial_penetration_um=surface["max_radial_penetration_um"],
                peak_point_pressure_MPa=surface["max_point_pressure_MPa"]))
        run.update(states=rows, load_path_sha256=digest(pathfile), barrel_sha256=digest(barrelfile),
                   residual_sha256=digest(residualfile))
        runs.append(run)
        native.append(locked_fields(case))
    coarse, fine = runs
    assert coarse["step_sha256"] == fine["step_sha256"] and coarse["bare_sha256"] == fine["bare_sha256"]
    assert coarse["times"] == fine["times"] and [r["mesh_size_mm"] for r in runs] == [2, 1.5]
    for a, b in zip(coarse["supports"], fine["supports"], strict=True):
        for key in ("case_center_mm", "board_center_mm", "screw_axis_mm", "grip_mm"):
            np.testing.assert_allclose(a[key], b[key], atol=1e-7, rtol=0)
        assert a["bearing_nodes"][0] == b["bearing_nodes"][0]
    base, ids0, u0, _ = native[0]
    control, ids1, u1, _ = native[1]
    fields = {}
    for name, materials in {"PCB": [208], "cells": BODIES,
                            "nickel_strips": [174, 179, 180, 186, 189, 193],
                            "washers": [173, 178, 181, 182, 183, 192]}.items():
        pair = []
        for raw in (base, control):
            g = raw.quadgrid
            select = np.isin(g.cell_data["ansys_elem_type_num"], [185, 186, 187]) & np.isin(g.cell_data["ansys_material_type"], materials)
            pair.append(np.unique(g.extract_cells(select).point_data["ansys_node_num"]))
        ids, check = pair
        np.testing.assert_array_equal(ids, check)
        xyz = base.mesh.nodes[positions(base.mesh.nnum, ids)]
        np.testing.assert_allclose(xyz, control.mesh.nodes[positions(control.mesh.nnum, ids)], atol=1e-12, rtol=0)
        fields[name] = differences(ids, 1000 * xyz, u0[positions(ids0, ids)], u1[positions(ids1, ids)])
    final0, final1 = coarse["states"][-1], fine["states"][-1]
    change = {key: 100 * (final1[key] / final0[key] - 1) for key in
              ("pocket_resultant_N", "loaded_quadrature_area_mm2", "peak_radial_penetration_um", "peak_point_pressure_MPa")}
    result = dict(runs=runs, locked_fine_vs_coarse_change_percent=change, matched_original_solids_at_lock=fields,
        scope="Native nylon installation on two case meshes at the same 0.01 N absolute force criterion. "
              "All saved states passed the existing mounting-force screens and independent loaded-face reconstruction. "
              "The quadrature area is a numerical contact measure. This pair measures sensitivity at these two mesh sizes.")
    write_json(AUDIT / "nylon_tight_mesh_comparison.json", result)
    print(change, fields["PCB"], flush=True)


if __name__ == "__main__":
    compare()

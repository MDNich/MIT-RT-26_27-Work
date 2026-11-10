"""Check native middle-cell preload against the deformed cylindrical barrel at every saved set."""

import argparse

import numpy as np
from case_stress import source
from early_cell_clearance import outer_faces
from film_identity import digest, write_json
from snug_board_pull import AUDIT, BODIES, CAMPAIGN, read
from snug_pocket_sampling import cylindrical_surfaces
from snug_preload_load_path import CASES
from snug_prescribed_contact import installation_history
from stage_snug_fit import input_record


def audit(case):
    proof, _, raw = source(case, CAMPAIGN)
    ref = input_record(case)
    balance_file = AUDIT / f"{case}_load_path.json"
    balance = read(balance_file)
    assert balance["rst_sha256"] == proof["rst_sha256"] and balance["input_sha256"] == ref["input_sha256"]
    node_ids = raw.mesh.nnum
    shell, cell = cylindrical_surfaces(ref, raw, node_ids, outer_faces(raw, [BODIES[1]]))
    frames = installation_history(case, raw, node_ids, shell, cell)
    for row, check in zip(frames, balance["states"], strict=True):
        assert row["native_set"] == check["native_set"] and row["time"] == check["time"]
        row["all_pockets_native_N"] = float(np.linalg.norm(check["native_contact_resultant_XYZ_N"]))
        row["mounting_force_balance_passed"] = check["within_existing_bearing_force_screens"]
        row["loaded_faces_match"] = row["geometry_faces"] == row["native_faces"]
        points = row["points"]
        row["loaded_quadrature_area_mm2"] = sum(p["integration_area_mm2"] for p in points)
        row["max_radial_penetration_um"] = max((p["radial_penetration_um"] for p in points), default=0)
        row["max_point_pressure_MPa"] = max((p["pressure_MPa"] for p in points), default=0)
        row["original_face_missing_at_barrel"] = sorted(set(row["native_faces"]) - set(row["geometry_faces"]))
    assert frames[-1]["time"] == 2 and np.isclose(frames[-1]["all_pockets_native_N"], frames[-1]["native_net_N"], atol=2e-7, rtol=1e-7)
    report = {
        "case": case,
        "input_sha256": ref["input_sha256"],
        "mesh_sha256": ref["mesh_sha256"],
        "rst_sha256": proof["rst_sha256"],
        "native_and_solid_balance_sha256": digest(balance_file),
        "barrel_case_triangles": len(shell[0]),
        "barrel_target_triangles": len(cell[0]),
        "states": frames,
        "scope": "Independent radial projection of three integration points per case triangle on the native "
        "deformed FE barrel. Loaded quadrature area sums the numerical integration weights. It is not a measured "
        "contact area. Native face forces include target rims beyond this radial projection. Overall force "
        "balance is checked separately against the mounts.",
    }
    write_json(AUDIT / f"{case}_barrel_tractions.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=CASES, nargs="+")
    for name in parser.parse_args().case:
        audit(name)

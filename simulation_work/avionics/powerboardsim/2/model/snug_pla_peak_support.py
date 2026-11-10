"""Count simultaneous coupon crossings and locate the governing PLA corner relative to the locked pocket."""

import argparse

import numpy as np
from case_stress import source
from film_identity import digest, write_json
from installation_material import PLA
from snug_board_pull import AUDIT, CAMPAIGN, positions, read
from snug_pla_vibration import full_coordinates, setup
from snug_unilateral_geometry import exact_faces
from startup_pla import values


def audit(variant):
    modal, folder, freq, preload, elements, nodes, base, shapes, xyz, distance, _ = setup(variant, CAMPAIGN)
    contact_path = AUDIT / f"{variant}_static_contacts.json"
    contact = read(contact_path)
    assert contact["rst_sha256"] == preload["rst_sha256"]
    group, = contact["contact_history"][-1]["loaded_case_faces"]
    assert group["STEP_face"] == 17
    _, _, static = source(variant + "_static", CAMPAIGN)
    faces = exact_faces(static, group["element_ids"])
    face_nodes = np.unique(faces)
    face_xyz = 1000 * static.mesh.nodes[positions(static.mesh.nnum, face_nodes)]
    axes = {}
    for axis in "XYZ":
        peak_path = AUDIT / f"{variant}_{axis}_PLA_independent.json"
        peaks = read(peak_path)
        q, coordinate_sha, input_sha = full_coordinates(variant, CAMPAIGN, "independent", axis, modal, folder, freq)
        assert peaks["native_basis_sha256"] == modal["rst_sha256"] and peaks["native_static_sha256"] == preload["rst_sha256"]
        assert peaks["coordinate_source_sha256"] == coordinate_sha and peaks["input_sha256"] == input_sha
        records = {}
        for name, fields in peaks["scopes"].items():
            eligible = np.ones(len(nodes), bool) if name == "all" else distance >= 2
            assert name in ("all", "2mm_from_bearing")
            records[name] = {}
            for metric, peak in fields.items():
                sample = peak["sample"]
                stress = values(q[sample:sample+1], base, shapes, metric).ravel()
                assert np.isclose(stress[eligible].max(), peak["maximum_MPa"], rtol=1e-10, atol=1e-9)
                match = (elements.repeat(4) == peak["element"]) & (nodes == peak["node"])
                idx, = np.flatnonzero(match)
                assert eligible[idx] and np.isclose(stress[idx], peak["maximum_MPa"], rtol=1e-10)
                crossings = eligible & (stress >= PLA[metric])
                per_tet = crossings.reshape(-1, 4).sum(axis=1)
                same_node = nodes == nodes[idx]
                records[name][metric] = {
                    "sample": sample, "time_s": peak["time_s"], "peak_MPa": peak["maximum_MPa"],
                    "peak_element": peak["element"], "peak_node": peak["node"], "xyz_mm": xyz[idx].tolist(),
                    "distance_to_constraint_mm": float(distance[idx]),
                    "node_on_locked_case_face": bool(np.any(face_nodes == nodes[idx])),
                    "nearest_locked_case_face_node_mm": float(np.linalg.norm(face_xyz - xyz[idx], axis=1).min()),
                    "corner_records_over_reference": int(crossings.sum()),
                    "elements_with_any_corner_over_reference": int(np.count_nonzero(per_tet)),
                    "elements_with_all_four_over_reference": int(np.count_nonzero(per_tet == 4)),
                    "tets_incident_to_peak_node": int(same_node.sum()),
                    "incident_tets_over_reference_at_peak_node": int(crossings[same_node].sum()),
                }
        axes[axis] = {"source_peaks_sha256": digest(peak_path), "scopes": records}
    write_json(AUDIT / f"{variant}_PLA_peak_support.json", {
        "variant": variant, "native_basis_sha256": modal["rst_sha256"], "native_static_sha256": preload["rst_sha256"],
        "contact_sha256": digest(contact_path), "locked_contact_faces": group["element_ids"], "PLA_tets": len(elements),
        "axes": axes, "scope": "Element-corner counts at each scope's own governing time in the independent "
        "fixed-contact history. Corners shared by adjacent tetrahedra retain their unaveraged stresses. "
        "The counts describe the elastic stress field at that instant. Fracture assessment requires "
        "the evolving contact state and printed-material failure behavior.",
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=("snug125_nylon", "snug125_aluminium", "snug125_nylon_mesh15", "snug125_aluminium_mesh15"))
    audit(parser.parse_args().variant)

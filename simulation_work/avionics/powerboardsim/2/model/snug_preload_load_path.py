"""Recover the pocket, four tab and battery-strip forces and moments through bolt installation."""

import argparse

import numpy as np
from case_stress import case_elements, source
from cell_attachment_force import bodies_and_bonds
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_board_pull import AUDIT, BODIES, CAMPAIGN, read
from snug_board_pull_seats import incident_tetrahedra, installation_displacements
from snug_mount_reactions import ring_nodes
from snug_pocket_equilibrium import solid_nodal_forces
from snug_spacer_bearing import PILOTS
from stage_snug_fit import PRELOAD_CONTROLS, STEP_HASH, input_record

CASES = (
    *PRELOAD_CONTROLS,
    "snug125_nylon_out2_static",
    "snug125_aluminium_out2_static",
    "snug125_nylon_mesh15_static",
    "snug125_nylon_tol001_static",
    "snug125_aluminium_mesh15_static",
)


def wrench(nodes, forces, xyz, origin, selected, sign):
    take = positions(nodes, selected)
    force = sign * forces[take]
    arm = 1000 * (xyz[take] - origin)
    return {
        "force_XYZ_N": force.sum(0).tolist(),
        "moment_XYZ_Nmm": np.cross(arm, force).sum(0).tolist(),
    }


def audit(case):
    spec = input_record(case)
    proof, folder, raw = source(case, CAMPAIGN)
    assert spec["step_sha256"] == STEP_HASH
    branch = "snug125_" + spec["material"]
    nominal = input_record(branch + "_static")
    assert spec["bare_model_sha256"] == nominal["bare_model_sha256"]
    deck = folder / "model.inp"
    verified(deck, spec["input_sha256"])
    contact_file = AUDIT / (case + "_contacts.json")
    seats_file = AUDIT / (
        (branch + "_installation_seats" if "_out2_" in case else case + "_seats") + ".json"
    )
    contact, seats = read(contact_file), read(seats_file)
    assert contact["rst_sha256"] == proof["rst_sha256"]
    verified(
        contact_file, seats.get("native_contact_audit_sha256") or seats["repeat_contact_audit_sha256"]
    )
    rings, _ = ring_nodes(deck.read_text())
    assert list(rings) == PILOTS[::2].tolist()
    patches = []
    numbers = raw.mesh.enum
    order = np.argsort(numbers)
    shell_elements = case_elements(raw, case.removesuffix("_static"))
    for row in contact["contact_history"]:
        faces = row["loaded_case_faces"]
        assert all(q["STEP_face"] == 17 for q in faces)
        element_ids = [n for q in faces for n in q["element_ids"]]
        patch = []
        for index in order[positions(numbers[order], np.array(element_ids, dtype=int))]:
            face = raw.mesh.elem[index][10:18]
            assert face[2] == face[3] == face[6]
            patch.extend(face[[0, 1, 2, 4, 5, 7]])
        patches.append(np.unique(np.asarray(patch, dtype=int)))
    surfaces = np.unique(np.concatenate([*rings.values(), *patches]))
    sel, ids, conn = incident_tetrahedra(raw, shell_elements, surfaces)
    bodies, bonds, _ = bodies_and_bonds(raw, BODIES)
    elements, cell_ids, cell_conn = bodies[191]
    ends = [p[0][1] for p in bonds.values() if p[0][0] == 191]
    assert len(ends) == 2
    free_cell = np.setdiff1d(cell_ids, np.concatenate(ends))
    points = np.union1d(cell_ids, ids)
    x0 = raw.mesh.nodes[positions(raw.mesh.nnum, points)]
    origin = raw.mesh.nodes[positions(raw.mesh.nnum, PILOTS[::2])].mean(0)
    ix, cx = positions(points, ids), positions(points, cell_ids)
    sets = list(range(1, raw.nsets + 1))
    reuse_full = (
        (folder.parents[2] / "post" / CAMPAIGN / case / "dpf_u" / ("sets_" + "_".join(map(str, sets))))
        .joinpath(f"set_{sets[-1]:04d}.json")
        .is_file()
    )
    movements = installation_displacements(
        case, proof, folder, sets, points, reuse_full, point_folder="installation_load_path"
    )
    history = []
    for k, patch, move, ref, native in zip(
        sets, patches, movements, seats["states"], contact["resultant_force_check"], strict=True
    ):
        assert k == ref["native_set"] == native["native_set"] and ref["time"] == raw.time_values[k - 1]
        xyz = x0 + move
        ff, _ = solid_nodal_forces(raw, sel, conn, ids, xyz[ix], k - 1)
        cf, _ = solid_nodal_forces(raw, elements, cell_conn.reshape(-1, 10), cell_ids, xyz[cx], k - 1)
        tabs = [wrench(ids, ff, xyz[ix], origin, ring, 1) for ring in rings.values()]
        np.testing.assert_allclose(
            [v["force_XYZ_N"] for v in tabs], ref["tab_load_XYZ_N"], atol=1e-8, rtol=1e-8
        )
        paths = {
            "four_tabs": {key: np.sum([t[key] for t in tabs], axis=0).tolist() for key in tabs[0]},
            "PLA_pocket": wrench(ids, ff, xyz[ix], origin, patch, -1),
            "middle_cell": wrench(cell_ids, cf, xyz[cx], origin, free_cell, 1),
        }
        strip_ends = [wrench(cell_ids, cf, xyz[cx], origin, e, -1) for e in ends]
        for key in tabs[0]:
            np.testing.assert_allclose(
                paths["middle_cell"][key],
                np.sum([w[key] for w in strip_ends], axis=0),
                rtol=0,
                atol=1e-7,
            )
        residual = {
            name: float(np.linalg.norm(np.array(v["force_XYZ_N"]) - native["force_xyz_N"]))
            for name, v in paths.items()
        }
        assert abs(residual["four_tabs"] - ref["four_tab_force_balance_residual_N"]) < 1e-8
        entry = {
            "native_set": k,
            "time": ref["time"],
            "native_contact_resultant_XYZ_N": native["force_xyz_N"],
            "solid_loads": paths,
            "four_tab_bearings": tabs,
            "two_strip_bonds_on_cell_sign_reversed": strip_ends,
            "difference_from_native_contact_N": residual,
            "tab_minus_pocket_moment_norm_Nmm": float(
                np.linalg.norm(
                    np.subtract(
                        paths["four_tabs"]["moment_XYZ_Nmm"], paths["PLA_pocket"]["moment_XYZ_Nmm"]
                    )
                )
            ),
            "cell_minus_pocket_moment_norm_Nmm": float(
                np.linalg.norm(
                    np.subtract(
                        paths["middle_cell"]["moment_XYZ_Nmm"], paths["PLA_pocket"]["moment_XYZ_Nmm"]
                    )
                )
            ),
            "within_existing_bearing_force_screens": ref["within_force_screens"],
        }
        history.append(entry)
    # Reproduce the independent full-volume recovery where an earlier locked-state control exists.
    eq_branch = case.removesuffix("_out2_static") if "_out2_" in case else case.removesuffix("_static")
    locked_path = AUDIT / (eq_branch + "_locked_pocket_equilibrium.json")
    if locked_path.is_file():
        locked = read(locked_path)
        for key, old in (
            ("four_tabs", "four_mounts"),
            ("PLA_pocket", "PLA_pocket"),
            ("middle_cell", "middle_cell"),
        ):
            np.testing.assert_allclose(
                history[-1]["solid_loads"][key]["force_XYZ_N"],
                -np.array(locked["force_into_shell_XYZ_N"][old]),
                rtol=1e-7,
                atol=1e-7,
            )
    result = {
        "case": case,
        "rst_sha256": proof["rst_sha256"],
        "input_sha256": spec["input_sha256"],
        "contact_sha256": digest(contact_file),
        "bearing_sha256": digest(seats_file),
        "moment_origin_m": origin.tolist(),
        "incident_case_elements": len(sel),
        "middle_cell_elements": len(elements),
        "states": history,
        "scope": "Signed forces on the cell, recovered from native solid stresses in the deformed mesh. Four tab "
        "reactions and opposite PLA pocket tractions use the same sign as the cell-side force. "
        "Moments use a common origin at the centroid of the four undeformed tab pilots. The strip bonds "
        "are ideal. The solver contact file gives an independent force vector at each state.",
    }
    write_json(AUDIT / (case + "_load_path.json"), result)
    print(
        case,
        [(r["time"], round(r["difference_from_native_contact_N"]["PLA_pocket"], 5)) for r in history],
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", nargs="+", choices=CASES)
    for c in parser.parse_args().case:
        audit(c)

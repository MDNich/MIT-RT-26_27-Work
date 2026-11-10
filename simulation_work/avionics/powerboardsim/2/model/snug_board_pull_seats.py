"""Resolve each spacer and M4 shank during the complete-board side-load cycle."""

import argparse
import re

import numpy as np
from case_stress import case_elements, source
from dpf_readback import export
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from native_rst import read_rst
from screw_vibration import screw_elements, section
from snug_board_pull import AUDIT, BRANCHES, CAMPAIGN, ROOT, read
from snug_mesh_comparison import force_pair
from snug_mount_reactions import ring_nodes
from snug_pocket_equilibrium import solid_nodal_forces
from snug_spacer_bearing import PILOTS, seat_stiffness
from stage_snug_fit import PRELOAD_CONTROLS, input_record
from tab_seating import read_point_file


def incident_tetrahedra(raw, elements, boundary_nodes):
    order = np.argsort(raw.mesh.enum)
    connectivity = np.stack(
        [raw.mesh.elem[j][10:20] for j in order[positions(raw.mesh.enum[order], elements)]]
    )
    # A surface nodal force includes every incident solid, including those touching it only at a vertex.
    use = np.isin(connectivity, boundary_nodes).any(axis=1)
    ids, inverse = np.unique(connectivity[use], return_inverse=True)
    return elements[use], ids, inverse.reshape(-1, 10)


class BearingSections:
    def __init__(self, branch, raw, deck):
        rings, _ = ring_nodes(deck)
        np.testing.assert_array_equal(list(rings), PILOTS[::2])
        all_ring_nodes = np.concatenate(list(rings.values()))
        assert len(all_ring_nodes) == len(np.unique(all_ring_nodes))
        solids = case_elements(raw, branch)
        self.elements, self.ids, self.conn = incident_tetrahedra(raw, solids, all_ring_nodes)
        self.rings = [positions(self.ids, r) for r in rings.values()]
        self.points = np.union1d(self.ids, PILOTS)
        self.solid_ix = positions(self.points, self.ids)
        self.pilot_ix = positions(self.points, PILOTS)
        self.x0 = raw.mesh.nodes[positions(raw.mesh.nnum, self.points)]
        ends = self.x0[self.pilot_ix].reshape(4, 2, 3)
        self.length = np.linalg.norm(ends[:, 1] - ends[:, 0], axis=1)
        self.k = seat_stiffness(deck)
        self.area = (
            np.pi * float(re.search(r"(?im)^SECTYPE,851,BEAM,CSOLID\s+SECDATA,([^,]+)", deck)[1]) ** 2
        )

    def read(self, raw, native_set, u_m, beam_positions):
        x = self.x0 + u_m
        v = np.diff(x[self.pilot_ix].reshape(4, 2, 3), axis=1)[:, 0]
        length = np.linalg.norm(v, axis=1)
        direction = v / length[:, None]
        gap = length - self.length
        compression = self.k * np.maximum(0, -gap)
        stress = section(raw, native_set - 1, beam_positions, "ENS")
        ends = stress[:, :, 0] * self.area
        np.testing.assert_allclose(stress.mean(axis=2) * self.area, ends, atol=1e-5, rtol=2e-5)
        direct = ends[:, 0]
        nodal, checks = solid_nodal_forces(
            raw, self.elements, self.conn, self.ids, x[self.solid_ix], native_set - 1
        )
        loads = np.array([nodal[ix].sum(axis=0) for ix in self.rings])
        projected = np.einsum("ij,ij->i", direction, loads)
        residual = projected - (direct - compression)
        return {
            "native_set": native_set,
            "signed_extension_nm": (gap * 1e9).tolist(),
            "spacer_compression_N": compression.tolist(),
            "shank_tab_end_tension_N": direct.tolist(),
            "shank_board_end_tension_N": ends[:, 1].tolist(),
            "tab_load_XYZ_N": loads.tolist(),
            "axial_tab_load_N": projected.tolist(),
            "axial_equilibrium_residual_N": residual.tolist(),
            "integration_check": checks,
        }


def compare_resultant(row, native):
    tab_force = np.sum(row["tab_load_XYZ_N"], axis=0)
    error = np.linalg.norm(tab_force - native)
    magnitude = np.linalg.norm(native)
    row["native_force_on_cells_XYZ_N"] = list(native)
    row["four_tab_force_balance_residual_N"] = float(error)
    row["relative_vector_residual"] = float(error / magnitude) if magnitude else None
    row["within_force_screens"] = bool(
        max(map(abs, row["axial_equilibrium_residual_N"])) < 0.004
        and error < 0.03
        and (magnitude == 0 or error < 0.05 * magnitude)
    )


def installation_displacements(
    case, proof, folder, sets, points, reuse_full_fields, point_folder="tab_load_points"
):
    if reuse_full_fields:
        fields = export(case, CAMPAIGN, sets)
        for k in sets:
            field = fields / f"set_{k:04d}"
            nodes = np.fromfile(field.with_suffix(".ids"), "<i4")
            order = np.argsort(nodes)
            u = np.fromfile(field.with_suffix(".u"), "<f8").reshape(-1, 3)
            yield u[order[positions(nodes[order], points)]]
    else:
        out = ROOT / ".runtime/post" / CAMPAIGN / case / point_folder
        u_mm, _ = read_point_file(folder / "file.rst", out, proof["rst_sha256"], sets, points.tolist())
        for u in u_mm:
            yield 0.001 * u


def check_installation(case, sections, previous_history=None):
    repeat, folder, raw = source(case, CAMPAIGN)
    contact_path = AUDIT / (case + "_contacts.json")
    contact = read(contact_path)
    assert contact["rst_sha256"] == repeat["rst_sha256"]
    sets = list(range(1, raw.nsets + 1))
    movements = installation_displacements(
        case, repeat, folder, sets, sections.points, previous_history is not None
    )
    beams = screw_elements(raw)[1]
    states = []
    for k, saved, u in zip(sets, contact["resultant_force_check"], movements, strict=True):
        assert saved["native_set"] == k
        r = sections.read(raw, k, u, beams)
        time = float(raw.time_values[k - 1])
        if previous_history is not None:
            previous = previous_history[k - 1]
            assert previous["set"] == k and previous["time"] == time
            np.testing.assert_allclose(
                r["signed_extension_nm"], previous["signed_seat_extension_nm"], atol=1e-5, rtol=0
            )
        compare_resultant(r, saved["force_xyz_N"])
        r["time"] = time
        states.append(r)
    worst = float(np.max(np.abs([r["axial_equilibrium_residual_N"] for r in states])))
    force_error = max(r["four_tab_force_balance_residual_N"] for r in states)
    print(
        case,
        "installation max tab axial and whole-case vector residual [N]",
        worst,
        force_error,
        flush=True,
    )
    return states, worst, force_error, contact_path


def check_preload_control(case):
    assert case in (
        *PRELOAD_CONTROLS,
        "snug125_nylon_tol001_static",
        "snug125_nylon_mesh15_static",
        "snug125_aluminium_mesh15_static",
    )
    proof, folder, raw = source(case, CAMPAIGN)
    spec = input_record(case)
    deck = folder / "model.inp"
    verified(deck, spec["input_sha256"])
    tighter = "absolute_force_criterion_N" in spec
    comparison_kind = "tolerance" if tighter else "mesh"
    control_kind = "tighter" if tighter else "refined"
    reference_case, comparison = force_pair(case)
    reference = AUDIT / (reference_case.replace("_out2_static", "_installation") + "_seats.json")
    pair = read(comparison)
    before, after = pair["runs"]
    assert after["case"] == case and after["rst_sha256"] == proof["rst_sha256"]
    assert after["input_sha256"] == spec["input_sha256"]
    assert before["case"] == reference_case
    original = read(reference)
    verified(
        AUDIT / (before["case"] + "_contacts.json"),
        original.get("repeat_contact_audit_sha256") or original["native_contact_audit_sha256"],
    )
    if tighter:
        assert (
            spec["absolute_force_criterion_N"] == 0.01
            and before["mesh_size_mm"] == after["mesh_size_mm"]
        )
    else:
        assert before["mesh_size_mm"] == 2 and after["mesh_size_mm"] == 1.5
    sections = BearingSections(case.removesuffix("_static"), raw, deck.read_text())
    # The equations can be recovered before modal extraction. If the same case already has an
    # archived bearing history, check all pilot separations against it.
    archived = AUDIT / (case.removesuffix("_static") + "_spacer_bearing.json")
    preload = read(archived) if archived.is_file() else None
    if preload is not None:
        assert preload["static_rst_sha256"] == proof["rst_sha256"]
        np.testing.assert_allclose(sections.k, preload["seat_stiffness_N_per_m"], rtol=1e-12, atol=0)
        np.testing.assert_allclose(sections.length, preload["unstrained_grip_m"], rtol=0, atol=1e-14)
    rows, worst, error, contacts = check_installation(
        case, sections, preload["history"] if preload else None
    )
    matched = []
    original_states = original["states"]
    for station in pair["matched_native_stations"]:
        old = original_states[station["coarse_set"] - 1]
        new = rows[station["fine_set"] - 1]
        assert abs(old["time"] - new["time"]) < 1e-9
        matched.append(
            {
                "load_time": old["time"],
                "original_case_vector_residual_N": old["four_tab_force_balance_residual_N"],
                f"{control_kind}_case_vector_residual_N": new["four_tab_force_balance_residual_N"],
                "original_pocket_resultant_N": float(
                    np.linalg.norm(old["native_force_on_cells_XYZ_N"])
                ),
                f"{control_kind}_pocket_resultant_N": float(
                    np.linalg.norm(new["native_force_on_cells_XYZ_N"])
                ),
            }
        )
    write_json(
        AUDIT / (case + "_seats.json"),
        {
            "case": case,
            "rst_sha256": proof["rst_sha256"],
            "input_sha256": spec["input_sha256"],
            "reference_sha256": digest(reference),
            "comparison_sha256": digest(comparison),
            "control_kind": comparison_kind,
            "native_contact_audit_sha256": digest(contacts),
            "matched_stations": matched,
            "states": rows,
            "states_outside_force_screens": [
                r["native_set"] for r in rows if not r["within_force_screens"]
            ],
            "max_axial_equilibrium_residual_N": worst,
            "max_case_vector_residual_N": error,
            "scope": "The same four bearing and complete-case force checks are applied at every native installation "
            "station. Only common load stations are paired. Stations outside the force screens remain diagnostic.",
        },
    )


def audit(branch, parent_only=False):
    parent, original, locked = source(branch + "_static", CAMPAIGN)
    preload_path = AUDIT / (branch + "_spacer_bearing.json")
    preload = read(preload_path)
    assert parent["rst_sha256"] == preload["static_rst_sha256"]
    deck = original / "model.inp"
    verified(deck, preload["deck_sha256"])
    sections = BearingSections(branch, locked, deck.read_text())
    np.testing.assert_allclose(sections.k, preload["seat_stiffness_N_per_m"], rtol=1e-12, atol=0)
    np.testing.assert_allclose(sections.length, preload["unstrained_grip_m"], rtol=0, atol=1e-14)
    k = locked.nsets
    field = export(parent["case"], CAMPAIGN, [k]) / f"set_{k:04d}"
    nodes = np.fromfile(field.with_suffix(".ids"), "<i4")
    us = np.fromfile(field.with_suffix(".u"), "<f8").reshape(-1, 3)
    order = np.argsort(nodes)
    baseline = sections.read(
        locked, k, us[order[positions(nodes[order], sections.points)]], screw_elements(locked)[1]
    )
    np.testing.assert_allclose(
        baseline["axial_tab_load_N"], preload["PLA_ring_projected_force_N"], atol=1e-7
    )
    mean_tension = np.mean(
        [baseline["shank_tab_end_tension_N"], baseline["shank_board_end_tension_N"]], axis=0
    )
    np.testing.assert_allclose(mean_tension, preload["beam_direct_force_N"], atol=1e-7)
    np.testing.assert_allclose(
        baseline["spacer_compression_N"], -np.array(preload["locked_seat_force_N"]), atol=1e-7
    )
    if parent_only:
        states, worst, force_error, contact_path = check_installation(
            branch + "_out2_static", sections, preload["history"]
        )
        assert states[-1]["within_force_screens"], states[-1]
        write_json(
            AUDIT / (branch + "_installation_seats.json"),
            {
                "branch": branch,
                "repeat_contact_audit_sha256": digest(contact_path),
                "installed_spacer_audit_sha256": digest(preload_path),
                "incident_tetrahedra": len(sections.elements),
                "max_axial_equilibrium_residual_N": worst,
                "max_case_vector_residual_N": force_error,
                "states_outside_force_screens": [
                    r["native_set"] for r in states if not r["within_force_screens"]
                ],
                "states": states,
                "scope": "Four axial tab balances and vector balance of the complete printed case against native contact "
                "forces at every converged tightening and locking station in the output-enabled static repeat. "
                "Screens use 0.004 N for a single axial bearing and 0.03 N for the case vector. "
                "A nonzero native contact resultant also requires a vector difference below five percent. "
                "Only passing stations support a balanced transmission of the reported pocket load.",
            },
        )
        return
    case = branch + "_cellpush_x"
    control_path = AUDIT / (case + ".json")
    control = read(control_path)
    assert control["parent_rst_sha256"] == parent["rst_sha256"]
    path = ROOT / ".runtime/archive" / CAMPAIGN / case / "file.rst"
    verified(path, control["rst_sha256"])
    raw = read_rst(path)
    sets = [r["native_set"] for r in control["states"]]
    out = ROOT / ".runtime/post" / CAMPAIGN / case / "tab_load_points"
    u, _ = read_point_file(path, out, control["rst_sha256"], sets, sections.points.tolist())
    independent_path = AUDIT / (branch + "_spacer_pocket_pull.json")
    independent = read(independent_path)
    assert independent["seat_preload_sha256"] == digest(preload_path)
    assert independent["contact_labels"][-4:] == [f"spacer {i}" for i in range(1, 5)]
    path_states = independent["paths"]["left_plus_X"]["states"]
    force = [r["applied_magnitude_N"] for r in path_states]
    predictions = np.array([r["projected_compression_N"][-4:] for r in path_states])
    assert np.all(np.diff(force) > 0)
    rows = []
    beams = screw_elements(raw)[1]
    for state, movement in zip(control["states"], u, strict=True):
        load = state["applied_X_N"]
        assert 0 <= load <= force[-1]
        r = sections.read(raw, state["native_set"], movement * 0.001, beams)
        r.update(time=state["time"], applied_X_N=load)
        if state["time"] == 2.0:
            for key in (
                "tab_load_XYZ_N",
                "spacer_compression_N",
                "shank_tab_end_tension_N",
                "shank_board_end_tension_N",
            ):
                np.testing.assert_allclose(r[key], baseline[key], atol=1e-7, rtol=0)
        if "native_case_contact_force" in state:
            compare_resultant(r, state["native_case_contact_force"]["CNF_XYZ_N"])
        r["installed_model_spacer_compression_N"] = [
            float(np.interp(load, force, f)) for f in predictions.T
        ]
        rows.append(r)
    worst = float(np.max(np.abs([r["axial_equilibrium_residual_N"] for r in rows])))
    print(case, "maximum four-bearing axial residual [N]", worst, flush=True)
    compared = [r for r in rows if "within_force_screens" in r]
    assert len(compared) == len(rows) - 1
    write_json(
        AUDIT / (case + "_seats.json"),
        {
            "case": case,
            "rst_sha256": control["rst_sha256"],
            "native_pull_sha256": digest(control_path),
            "installed_spacer_audit_sha256": digest(preload_path),
            "independent_path_sha256": digest(independent_path),
            "dpf_displacement_sha256": digest(out / "displacements.bin"),
            "incident_tetrahedra": len(sections.elements),
            "max_axial_equilibrium_residual_N": worst,
            "states_outside_force_screens": [
                r["native_set"] for r in compared if not r["within_force_screens"]
            ],
            "states": rows,
            "scope": "Spacer forces recovered from actual pilot spacing and the compression-only law. "
            "Signed shank tensions come from native beam stresses. Independently integrated PLA bearing forces "
            "supply an axial balance at each tab. The M4 screws start stress free.",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branches", choices=BRANCHES[1:], nargs="+")
    parser.add_argument("--parent-only", action="store_true")
    args = parser.parse_args()
    for branch in args.branches:
        audit(branch, args.parent_only)

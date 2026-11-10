"""Check both sides of the six ideal nickel bonds during the whole-board left-cell load."""

import argparse

import numpy as np
from case_stress import source
from cell_attachment_force import bodies_and_bonds
from dpf_readback import export
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from native_rst import read_rst
from snug_board_pull import AUDIT, BODIES, BRANCHES, CAMPAIGN, ROOT, mass_weights, read
from snug_pocket_equilibrium import solid_nodal_forces
from tab_seating import read_point_file


class BondSections:
    def __init__(self, raw, branch):
        mass_ids, W, proof = mass_weights(branch)
        bodies, self.bonds, _ = bodies_and_bonds(raw, proof["geometry"])
        ordered = np.concatenate([part[1] for part in bodies.values()])
        self.ids = np.sort(ordered)
        assert len(self.ids) == len(np.unique(self.ids))
        elements = []
        connect = []
        for numbers, nodes, index in bodies.values():
            elements.extend(numbers)
            connect.append(nodes[index.reshape(-1, 10)])
        order = np.argsort(elements)
        self.elements = np.asarray(elements)[order]
        self.conn = positions(self.ids, np.vstack(connect)[order])
        self.positions = raw.mesh.nodes[positions(raw.mesh.nnum, self.ids)]
        self.weights = np.zeros(len(self.ids))
        self.weights[positions(self.ids, mass_ids)] = W[0]
        np.testing.assert_allclose(self.weights.sum(), 1, atol=1e-12)
        self.pairs = {
            real: [positions(self.ids, body_nodes) for _, body_nodes in ends]
            for real, ends in self.bonds.items()
        }
        self.strip_body = {
            int(s["native_material"]): int(s["STEP_body"])
            for s in read(ROOT / "validation/rigid_case_drawdown.json")["records"]
        }
        self.tangent_path = AUDIT / f"{branch}_initial_cell_load_paths.json"
        self.tangent = read(self.tangent_path)
        assert self.tangent["load_order"] == ["left", "middle", "right"]

    def state(self, raw, xyz, station, load):
        """Port forces from independent virtual work of deformed solid stresses on the two different meshes."""
        F, checks = solid_nodal_forces(raw, self.elements, self.conn, self.ids, xyz, station)
        bonded = {}
        for pid, (cell, strip) in self.pairs.items():
            (cellmat, _), (stripmat, _) = self.bonds[pid]
            nodal_load = np.array([load * self.weights[cell].sum(), 0, 0])
            from_cell = F[cell].sum(0) - nodal_load
            from_strip = -F[strip].sum(0)
            bonded[pid] = {
                "cell": ("left", "middle", "right")[BODIES.index(cellmat)],
                "strip_STEP_body": self.strip_body[stripmat],
                "distributed_load_on_bond_nodes_N": nodal_load.tolist(),
                "force_on_cell_from_cell_side_N": from_cell.tolist(),
                "force_on_cell_from_strip_side_N": from_strip.tolist(),
                "two_side_vector_residual_N": float(np.linalg.norm(from_cell - from_strip)),
            }
        return bonded, checks


def original(branch):
    case = branch + "_static"
    parent, _, raw = source(case, CAMPAIGN)
    sections = BondSections(raw, branch)
    n = raw.nsets
    d = export(case, CAMPAIGN, [n]) / f"set_{n:04d}"
    node = np.fromfile(d.with_suffix(".ids"), "<i4")
    u = np.fromfile(d.with_suffix(".u"), "<f8").reshape(-1, 3)
    order = np.argsort(node)
    bonds, _ = sections.state(
        raw, sections.positions + u[order[positions(node[order], sections.ids)]], n - 1, 0.0
    )
    return parent, bonds


def audit(branch, parent_only=False):
    parent, baseline = original(branch)
    if parent_only:
        print(
            branch, [(p, round(v["two_side_vector_residual_N"], 5)) for p, v in baseline.items()], flush=True
        )
        return
    case = branch + "_cellpush_x"
    report = AUDIT / (case + ".json")
    verified_case = read(report)
    assert verified_case["parent_rst_sha256"] == parent["rst_sha256"] and verified_case["case"] == case
    file = ROOT / ".runtime/archive" / CAMPAIGN / case / "file.rst"
    verified(file, verified_case["rst_sha256"])
    raw = read_rst(file)
    s = BondSections(raw, branch)
    sets = [v["native_set"] for v in verified_case["states"]]
    out = ROOT / ".runtime/post" / CAMPAIGN / case / "bond_stations"
    displacement, _ = read_point_file(file, out, verified_case["rst_sha256"], sets, s.ids.tolist())
    records = []
    zero = None
    zero_other = False
    for v, u in zip(verified_case["states"], displacement, strict=True):
        load = v["applied_X_N"]
        bonds, checks = s.state(raw, s.positions + u * 0.001, v["native_set"] - 1, load)
        if v["time"] == 2.0:
            for p, values in bonds.items():
                for key in ("force_on_cell_from_cell_side_N", "force_on_cell_from_strip_side_N"):
                    np.testing.assert_allclose(values[key], baseline[p][key], rtol=0, atol=1e-7)
        if v["time"] == 3.0:
            zero = bonds
            zero_other = any(face["STEP_face"] != 17 for face in v.get("loaded_case_faces", []))
        row = {
            "time": v["time"],
            "native_set": v["native_set"],
            "applied_X_N": load,
            "bonds": bonds,
            "element_checks": checks,
        }
        if zero is not None:
            inc = {}
            for p, b in bonds.items():
                for side in ("cell", "strip"):
                    key = f"force_on_cell_from_{side}_side_N"
                    b[side + "_increment_from_hold_N"] = (np.array(b[key]) - zero[p][key]).tolist()
                tangent = -load * np.array(s.tangent["element_group_XYZ_N_per_N"][f"strip {p}"])[:, 0]
                b["installed_tangent_prediction_N"] = tangent.tolist()
                b["nonlinear_minus_tangent_N"] = (
                    np.array(b["strip_increment_from_hold_N"]) - tangent
                ).tolist()
                b["two_side_increment_residual_N"] = float(
                    np.linalg.norm(
                        np.array(b["cell_increment_from_hold_N"]) - b["strip_increment_from_hold_N"]
                    )
                )
            for i, cell in enumerate(("left", "middle", "right")):
                strip = sum(
                    np.array(b["strip_increment_from_hold_N"]) for b in bonds.values() if b["cell"] == cell
                )
                # The whole-case native force readback distinguishes the middle pocket. For a case with contact
                # elsewhere the other two cell resultants cannot be separated with this record.
                add = np.array([load if i == 0 else 0.0, 0, 0])
                case_load = np.zeros(3)
                if branch != "bare":
                    step = v["native_middle_pocket_force"]
                    if cell == "middle":
                        case_load = np.array(step["change_from_zero_hold_XYZ_N"])
                    elif zero_other or any(face["STEP_face"] != 17 for face in v["loaded_case_faces"]):
                        inc[cell] = {
                            "net_bond_increment_XYZ_N": strip.tolist(),
                            "case_force_not_separately_identified": True,
                        }
                        continue
                inc[cell] = {
                    "net_bond_increment_XYZ_N": strip.tolist(),
                    "applied_N": add.tolist(),
                    "case_increment_N": case_load.tolist(),
                    "increment_balance_residual_N": float(np.linalg.norm(strip + add + case_load)),
                }
            row["cells"] = inc
        records.append(row)
    max_pair = max(
        v["two_side_increment_residual_N"] for r in records if "cells" in r for v in r["bonds"].values()
    )
    max_body = max(
        v["increment_balance_residual_N"]
        for r in records
        if "cells" in r
        for v in r["cells"].values()
        if "increment_balance_residual_N" in v
    )
    print(
        case, "largest recovered incremental pair and whole-cell residual N", max_pair, max_body, flush=True
    )
    assert max_pair < 0.03 and max_body < 0.03, (max_pair, max_body)
    write_json(
        AUDIT / (case + "_bonds.json"),
        {
            "case": case,
            "rst_sha256": verified_case["rst_sha256"],
            "parent_rst_sha256": parent["rst_sha256"],
            "installed_tangent_sha256": digest(s.tangent_path),
            "native_pull_sha256": digest(report),
            "displacements_sha256": digest(out / "displacements.bin"),
            "max_incremental_pair_residual_N": max_pair,
            "max_incremental_cell_residual_N": max_body,
            "states": records,
            "scope": "Independent integration of native deformed solid stresses on the two sides of each ideal bonded interface. "
            "Cell-side resultants subtract the mass-weighted applied force on its bond nodes. Increments use the converged "
            "zero-added-load hold. The model has no measured weld strength or separate spot-weld geometry.",
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("branches", nargs="+", choices=BRANCHES)
    p.add_argument("--parent-only", action="store_true")
    a = p.parse_args()
    for b in a.branches:
        audit(b, a.parent_only)

"""Recover component stresses in the installed board during the force-controlled left-cell load."""

import argparse
import re

import numpy as np
from case_fit import GROUPS
from case_stress import case_elements, printed_compliance, source
from film_identity import digest, verified, write_json
from installation_material import PLA
from local_equilibrium import positions
from native_rst import read_rst
from nickel_vibration import element_set
from pcb_dynamic_stress import equivalent
from pcb_installation import maximum_principal_strain
from snug_board_pull import AUDIT, BRANCHES, CAMPAIGN, ROOT, read


def property_value(deck, name, material):
    (value,) = re.findall(rf"(?im)^mp,{name},{material},([^,\s]+)", deck)
    return float(value)


def arrays(indices, elements, group, data, nodes, cols):
    ids = np.concatenate([nodes[j] for j in indices])
    en = np.repeat(elements, [len(nodes[j]) for j in indices])
    fields = np.concatenate([data[j].reshape(len(nodes[j]), cols) for j in indices])
    if group in ("nickel", "PLA"):
        assert len(ids) == 4 * len(elements)
    assert np.all(np.isfinite(fields))
    return en, ids, fields.astype(float)


class Materials:
    def __init__(self, branch, raw, deck):
        self.branch = branch
        self.deck = deck
        mapping = read(ROOT / "validation/rigid_case_drawdown.json")
        self.strip_ids = {
            r["native_material"]: r["STEP_body"]
            for r in mapping["records"]
            if r["STEP_body"] in GROUPS["nickel"]
        }
        assert len(self.strip_ids) == 6
        nickel, mat = element_set(raw, self.strip_ids)
        self.ni_material = np.repeat(mat, 4)
        self.nickel_by_mat = np.array([self.strip_ids[m] for m in self.ni_material])
        grid = raw.grid.cell_data
        board = grid["ansys_material_type"] == 208
        assert set(grid["ansys_elem_type_num"][board]) <= {185, 186, 187}
        self.bodies = {"nickel": nickel, "PCB": np.sort(grid["ansys_elem_num"][board])}
        self.elastic = {}
        for body, mats in (("nickel", self.strip_ids), ("PCB", [208])):
            props = {(property_value(deck, "EX", m), property_value(deck, "NUXY", m)) for m in mats}
            (self.elastic[body],) = props
        if branch != "bare":
            self.bodies["PLA"] = case_elements(raw, branch)
            self.bodies["shank"] = np.sort(grid["ansys_elem_num"][grid["ansys_etype"] == 851])
            assert len(self.bodies["shank"]) == 4
            self.C, self.G = printed_compliance(deck)
            self.screw_E = property_value(deck, "EX", 851)
        self.corner_ids = {}
        self.nodes = raw.mesh.nnum
        self.xyz_mm = raw.mesh.nodes * 1000

    def fields(self, raw, index):
        # ENS and EEL are the native unaveraged element-corner records at the same state.
        en, S, snodes = raw.element_solution_data(int(index), "ENS")
        ee, E, enodes = raw.element_solution_data(int(index), "EEL")
        metrics = {}
        errors = {}
        stresses = {}
        for name, els in self.bodies.items():
            si, ei = positions(en, els), positions(ee, els)
            if name == "shank":
                nodes = np.stack([snodes[i] for i in si])
                np.testing.assert_array_equal(nodes, np.stack([enodes[i] for i in ei]))
                np.testing.assert_array_equal(nodes, np.arange(950001, 950009).reshape(4, 2))
                axial = np.stack([S[i] for i in si]).reshape(4, 2, 25, 3)[:, :, :, 0].astype(float)
                strain = np.stack([E[i] for i in ei]).reshape(4, 2, 25, 3)[:, :, :, 0].astype(float)
                errors[name] = float(abs(axial - self.screw_E * strain).max() / max(1.0, abs(axial).max()))
                assert errors[name] < 1e-3
                mean = axial.mean(2)
                np.testing.assert_allclose(mean, axial[:, :, 0], rtol=2e-5, atol=10.0)
                sites = (np.repeat(els, 50), np.repeat(nodes.ravel(), 25))
                metrics["shank_fibre_tension_MPa"] = (axial * 1e-6).ravel()
                stresses[name] = axial
            else:
                numbers, ids, stress = arrays(si, els, name, S, snodes, 6)
                check, cn, eps = arrays(ei, els, name, E, enodes, 7)
                np.testing.assert_array_equal(numbers, check)
                np.testing.assert_array_equal(ids, cn)
                sites = (numbers, ids)
                stresses[name] = stress
                if name == "PLA":
                    predicted = np.column_stack((stress[:, :3] @ self.C, stress[:, 3:] / self.G))
                    x, y, z, xy = stress[:, :4].T
                    metrics["PLA_layer_tension_MPa"] = z * 1e-6
                    metrics["PLA_in_plane_tension_MPa"] = (0.5 * (x + y) + np.hypot(0.5 * (x - y), xy)) * 1e-6
                else:
                    young, nu = self.elastic[name]
                    predicted = np.column_stack(
                        (
                            ((1 + nu) * stress[:, :3] - nu * stress[:, :3].sum(1)[:, None]) / young,
                            2 * (1 + nu) * stress[:, 3:] / young,
                        )
                    )
                    metrics[name + "_equivalent_MPa"] = equivalent(stress) * 1e-6
                    if name == "PCB":
                        metrics["PCB_principal_tensile_microstrain"] = (
                            maximum_principal_strain(eps[:, :6]) * 1e6
                        )
                errors[name] = float(
                    np.linalg.norm(predicted - eps[:, :6]) / max(1e-12, np.linalg.norm(eps[:, :6]))
                )
                assert errors[name] < 1e-3, (name, index, errors[name])
            if name in self.corner_ids:
                for a, b in zip(sites, self.corner_ids[name], strict=True):
                    np.testing.assert_array_equal(a, b)
            else:
                self.corner_ids[name] = sites
        return metrics, stresses, errors

    def peak(self, field, metric, ix):
        body = metric.split("_", 1)[0]
        elements, nodes = self.corner_ids[body]
        where = int(ix[np.argmax(field[ix])])
        item = {
            "value": float(field[where]),
            "element": int(elements[where]),
            "node": int(nodes[where]),
            "reference_xyz_mm": self.xyz_mm[positions(self.nodes, [nodes[where]])[0]].tolist(),
        }
        if body == "nickel":
            item["strip_STEP_body"] = int(self.nickel_by_mat[where])
        if body == "shank":
            item["section_site"] = int(where % 25 + 1)
        return item

    def summary(self, metrics, reference):
        results = {}
        for metric, field in metrics.items():
            body = metric.split("_", 1)[0]
            scopes = {"all": np.arange(len(field))}
            if body == "nickel":
                scopes.update(
                    {str(m): np.flatnonzero(self.nickel_by_mat == m) for m in sorted(self.strip_ids.values())}
                )
            if body == "PCB":
                z = self.xyz_mm[positions(self.nodes, self.corner_ids["PCB"][1]), 2]
                scopes.update(
                    {
                        side: np.flatnonzero(np.isclose(z, height, atol=1e-6, rtol=0))
                        for side, height in (("low_Z", z.min()), ("high_Z", z.max()))
                    }
                )
            if body == "shank":
                scopes.update({str(i + 1): np.arange(i * 50, (i + 1) * 50) for i in range(4)})
            delta = field - reference[metric]
            by_scope = {}
            for name, ids in scopes.items():
                total = self.peak(field, metric, ids)
                rise = self.peak(delta, metric, ids)
                by_scope[name] = {"sites": len(ids), "largest_total": total, "largest_same_site_rise": rise}
            results[metric] = by_scope
        return results


def check_parent(branch, material, metrics):
    nickel = read(ROOT / "validation/nickel_vibration" / f"{branch}_X.json")
    for step, ref in nickel["strips"].items():
        select = material.nickel_by_mat == int(step)
        np.testing.assert_allclose(
            metrics["nickel_equivalent_MPa"][select].max(), ref["max_static_equivalent_MPa"], rtol=1e-7
        )
    if branch != "bare":
        parent = read(ROOT / "validation/installation_material" / (branch + "_static.json"))["history"][-1]
        for name in ("in_plane_tension_MPa", "layer_tension_MPa"):
            np.testing.assert_allclose(metrics["PLA_" + name].max(), parent["all_" + name], rtol=2e-6)
        np.testing.assert_allclose(
            metrics["shank_fibre_tension_MPa"].reshape(4, -1).max(1),
            parent["four_screws"]["peak_fiber_tension_MPa"],
            rtol=2e-6,
        )
    return nickel


def audit(branch, parent_only=False):
    case = branch + "_cellpush_x"
    parent = branch + "_static"
    proof, folder, rst = source(parent, CAMPAIGN)
    parent_ledger = read(ROOT / ".runtime/receipts" / CAMPAIGN / parent / "archived.json")
    hashes = {r["name"]: r["sha256"] for r in parent_ledger["files"]}
    verified(folder / "model.inp", hashes["model.inp"])
    mats = Materials(branch, rst, (folder / "model.inp").read_text())
    parent_metrics, parent_stress, parent_errors = mats.fields(rst, rst.nsets - 1)
    nickel = check_parent(branch, mats, parent_metrics)
    assert nickel["static_rst"] == proof["rst_sha256"]
    if parent_only:
        print(branch, "bolt-lock controls", parent_errors, flush=True)
        return
    control_file = AUDIT / (case + ".json")
    data = read(control_file)
    assert data["parent_rst_sha256"] == proof["rst_sha256"] and data["case"] == case
    native_dir = ROOT / ".runtime/archive" / CAMPAIGN / case
    verified(native_dir / "file.rst", data["rst_sha256"])
    raw = read_rst(native_dir / "file.rst")
    for key, els in Materials(branch, raw, mats.deck).bodies.items():
        np.testing.assert_array_equal(els, mats.bodies[key])
    states = data["states"]
    first = states[0]["native_set"]
    assert first == rst.nsets and states[0]["time"] == 2.0
    _, retained, _ = mats.fields(raw, first - 1)
    for key, fields in parent_stress.items():
        np.testing.assert_array_equal(fields, retained[key])
    zero = next(r["native_set"] for r in states if r["time"] == 3.0)
    baseline, _, _ = mats.fields(raw, zero - 1)
    result = []
    max_error = parent_errors.copy()
    for state in states:
        k = state["native_set"]
        values, _, errors = mats.fields(raw, k - 1)
        for key, err in errors.items():
            max_error[key] = max(max_error[key], err)
        entry = {v: state[v] for v in ("native_set", "time", "load_step", "applied_X_N")}
        entry["metrics"] = mats.summary(values, baseline)
        result.append(entry)
    checks = {
        "nickel_yield_reference_MPa": nickel["trial_reference_yield_MPa"],
        "printed_coupon_means_MPa": {k: PLA[k] for k in ("layer_tension_MPa", "in_plane_tension_MPa")},
    }
    if branch == "bare":
        checks.pop("printed_coupon_means_MPa")
    write_json(
        AUDIT / (case + "_stresses.json"),
        {
            "case": case,
            "direct_pull_audit_sha256": digest(control_file),
            "rst_sha256": data["rst_sha256"],
            "parent_rst_sha256": proof["rst_sha256"],
            "parent_deck_sha256": hashes["model.inp"],
            "native_section_checks": max_error,
            "references": checks,
            "states": result,
            "scope": "Unaveraged native quantities on the whole installed board. Same-site rise is the local scalar "
            "at that state minus its scalar at the zero-added-load hold, maximized over the same sites. "
            "Nickel in this model is linear elastic. Its local-study yield reference and the printed PLA "
            "coupon means are screening values. PCB strain and beam fibre tension have no verified hardware allowable.",
        },
    )
    print(
        case,
        [(r["time"], r["metrics"]["nickel_equivalent_MPa"]["all"]["largest_total"]["value"]) for r in result],
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branches", nargs="+", choices=BRANCHES)
    parser.add_argument("--parent-only", action="store_true")
    args = parser.parse_args()
    for branch in args.branches:
        audit(branch, args.parent_only)

"""Recover lateral actuator work, element stiffness energies and nodal-force work in the local pull."""

import argparse
from pathlib import Path

import numpy as np
from ansys.mapdl import reader
from audit_local import ROOT, read
from compare_pull import series
from dpf_readback import export_file
from film_identity import digest, write_json
from local_equilibrium import positions
from stage_snug_fit import AUDIT


def dofs(nodes, count):
    return (8 * nodes[:, :, None] + np.arange(count)).reshape(len(nodes), -1)


class WorkGroup:
    """Map the physical ENF slots in one MAPDL element group onto common node/DOF identities."""

    def __init__(self, raw, numbers, kind):
        order = np.argsort(raw.mesh.enum)
        self.ids = np.sort(numbers)
        elements = raw.mesh.elem
        rows = [elements[j] for j in order[positions(raw.mesh.enum[order], self.ids)]]
        connectivity = [e[10:] for e in rows]
        self.kind = kind
        count = 10 if kind == 850 else 4 if kind == 1 else 9 if kind in (3, 862) else 2
        self.contacts = kind in (3, 862)
        if self.contacts:
            target_type = 4 if kind == 3 else 861
            pilot_by_pair = {e[2]: e[10] for e in elements if e[1] == target_type and e[7] == 99}
            pilots = np.array([pilot_by_pair[e[2]] for e in rows])
            for raw_nodes, pilot in zip(connectivity, pilots, strict=True):
                if len(raw_nodes) > 8:
                    assert raw_nodes[8] == pilot
            nodes = np.column_stack((np.stack([row[:8] for row in connectivity]), pilots))
        else:
            nodes = np.stack([row[:count] for row in connectivity])
        if self.contacts:
            keys = np.column_stack((dofs(nodes[:, :8], 3), dofs(nodes[:, 8:9], 6)))
            assert np.all(nodes[:, 8] > 0)
        else:
            keys = dofs(nodes, 3 if kind in (850, 854) else 6)
        self.width = keys.shape[1]
        self.keys, inv = np.unique(keys, return_inverse=True)
        self.inverse = inv.reshape(keys.shape)
        self.virtual = self.keys // 8 == 0
        self.pilot = (
            np.isin(self.keys // 8, nodes[:, 8]) if self.contacts else np.zeros(len(self.keys), bool)
        )
        self.last_force = None
        self.last_motion = None
        self.work = np.zeros(2)
        self.max_internal = 0.0
        self.max_contact_force_residual = 0.0

    def set_field_indices(self, field_keys):
        self.mappings = []
        for offset, numbers in zip([0, 3], field_keys, strict=True):
            k = np.flatnonzero(
                (~self.virtual) & (self.keys % 8 >= offset) & (self.keys % 8 < offset + 3)
            )
            row = positions(numbers, self.keys[k] // 8)
            self.mappings.append((k, row, self.keys[k] % 8 - offset))

    def integrate(self, en, records, fields):
        indices = positions(en, self.ids)
        valid = np.array(
            [r for r, i in enumerate(indices) if records[i] is not None and len(records[i])], dtype=int
        )
        if self.kind in (850, 851, 1, 2):
            assert len(valid) == len(self.ids)
        total = np.zeros(len(self.keys))
        if len(valid):
            vals = np.stack([records[i] for i in indices[valid]])
            assert vals.shape[1] >= self.width
            if vals.shape[1] > self.width:
                assert self.kind in (851, 2)
                ratio = abs(vals[:, self.width :]).max() / max(1.0, abs(vals[:, : self.width]).max())
                assert ratio < 1e-5
                self.max_internal = max(self.max_internal, float(ratio))
            val = vals[:, : self.width]
            if self.contacts:
                error = np.max(abs(val[:, :24].reshape(-1, 8, 3).sum(1, dtype=float) + val[:, 24:27]))
                assert error < 0.005
                self.max_contact_force_residual = max(self.max_contact_force_residual, float(error))
            total = np.bincount(self.inverse[valid].ravel(), weights=val.ravel(), minlength=len(total))
        assert not self.virtual.any() or abs(total[self.virtual]).max() < 1e-9
        motion = np.zeros_like(total)
        for f, (take, rows, cols) in zip(fields, self.mappings, strict=True):
            motion[take] = f[rows, cols]
        if self.last_force is not None:
            dw = -0.5 * (total + self.last_force) * (motion - self.last_motion)
            self.work += [np.sum(dw[~self.pilot]), np.sum(dw[self.pilot])]
        self.last_force = total
        self.last_motion = motion
        return self.work.copy()

    def energy(self, numbers, values):
        idx = positions(numbers, self.ids)
        records = [values[i] for i in idx if values[i] is not None and len(values[i])]
        if self.kind in (850, 851, 1, 2):
            assert len(records) == len(idx)
        if not records:
            return np.zeros(2)
        a = np.stack(records)
        assert a.shape[1] == 11 and abs(a[:, 3]).max() < 1e-10
        return a[:, [1, 2]].sum(0, dtype=float)


def groups(raw):
    grid = raw.grid.cell_data
    n = grid["ansys_elem_num"]
    t = grid["ansys_etype"]
    rc = grid["ansys_real_constant"]
    assert set(t).issubset({1, 2, 3, 4, 850, 851, 854, 861, 862})
    labels = {
        1: "nickel",
        2: "rigid_cell_attachments",
        3: "strip_to_washers",
        850: "PLA",
        851: "shanks",
        854: "seats",
    }
    parts = {name: WorkGroup(raw, n[t == k], k) for k, name in labels.items() if (t == k).any()}
    if (t == 862).any():
        for pair, name in [(861, "moving_cell_to_PLA"), (862, "fixed_hardware_to_PLA")]:
            parts[name] = WorkGroup(raw, n[(t == 862) & (rc == pair)], 862)
    return parts


def history(path, sha, out, case, campaign, stations):
    raw = reader.read_binary(str(path))
    parts = groups(raw)
    sets = [r["native_set"] for r in stations]
    assert sets == list(range(sets[0], sets[-1] + 1))
    step = raw._resultheader["ls_table"][np.array(sets) - 1, 0]
    assert step[0] == 2 and np.all(step[1:] >= 3) and np.all(np.diff(step) >= 0)
    files = []
    for field, unit in [("U", "mm"), ("ROT", "rad")]:
        spec = {
            "case": case,
            "campaign": campaign,
            "source_sha256": sha,
            "sets": sets,
            "field": field,
            "unit": unit,
        }
        files.append(export_file(path, out / field, spec))
    ids_orig = None
    order = None
    history = []
    reference = None
    last = None
    actuator = 0.0
    for row in stations:
        k = row["native_set"]
        field = []
        ids = []
        hashes = {}
        for folder, extension in zip(files, ["u", "rot"], strict=True):
            stem = folder / f"set_{k:04d}"
            idx = stem.with_suffix(".ids")
            vec = stem.with_suffix("." + extension)
            ids.append(np.fromfile(idx, "<i4"))
            field.append(np.fromfile(vec, "<f8").reshape(-1, 3))
            hashes[extension] = [digest(idx), digest(vec)]
        if ids_orig is None:
            ids_orig = ids
            order = [np.argsort(v) for v in ids]
            for part in parts.values():
                part.set_field_indices([v[j] for v, j in zip(ids, order, strict=True)])
        else:
            for a, b in zip(ids_orig, ids, strict=True):
                np.testing.assert_array_equal(a, b)
        field = [v[j] for v, j in zip(field, order, strict=True)]
        x = float(field[0][positions(ids[0][order[0]], [2481])[0], 0])
        rf, node, dof = raw.nodal_reaction_forces(k - 1)
        f = float(rf[(node == 2481) & (dof == 1)].sum())
        assert abs(x - row["travel_mm"]) < 1e-8 and abs(f - row["cell_force_N"]) < 2e-5
        if last:
            actuator += (x - last[0]) * (f + last[1]) / 2
        last = (x, f)
        n, forces, _ = raw.element_solution_data(k - 1, "ENF")
        m, energies, _ = raw.element_solution_data(k - 1, "ENG")
        work = {name: part.integrate(n, forces, field) for name, part in parts.items()}
        ene = {name: part.energy(m, energies) for name, part in parts.items()}
        if reference is None:
            reference = ene
        ene = {key: v - reference[key] for key, v in ene.items()}
        w = {name: float(v.sum()) for name, v in work.items()}
        se = {name: float(v[0]) for name, v in ene.items()}
        history.append(
            {
                "native_set": k,
                "travel_mm": x,
                "cell_force_N": f,
                "actuator_work_mJ": actuator,
                "summed_force_work_mJ": sum(w.values()),
                "work_by_group_mJ": w,
                "contact_pilot_work_mJ": {
                    name: float(v[1]) for name, v in work.items() if parts[name].contacts
                },
                "stiffness_energy_change_mJ": se,
                "artificial_energy_change_mJ": {name: float(v[1]) for name, v in ene.items()},
                "field_sha256": hashes,
            }
        )
    return {
        "case": case,
        "rst_sha256": sha,
        "history": history,
        "component_checks": {
            key: {
                "max_unused_internal_force_fraction": p.max_internal,
                "max_face_pilot_force_mismatch_N": p.max_contact_force_residual,
            }
            for key, p in parts.items()
        },
    }


def field_cache(case, campaign, sha, stations):
    return (
        ROOT
        / ".runtime/post"
        / campaign
        / case
        / "pull_work"
        / sha[:16]
        / f"sets_{stations[0]['native_set']}_{stations[-1]['native_set']}"
    )


def evaluate(folder, sha, case, campaign, stations):
    out = field_cache(case, campaign, sha, stations)
    return history(folder / "pull.rst", sha, out, case, campaign, stations)


def closed_series(case, campaign, verdict=None):
    proof, series_rows = series(case, proof_path=verdict)
    assert proof["campaign"] == campaign
    station = [
        {"native_set": r["set"], "travel_mm": r["ux_mm"], "cell_force_N": r["cell_force_N"]}
        for r in series_rows
    ]
    return evaluate(
        ROOT / ".runtime/archive" / campaign / case, proof["rst_sha256"], case, campaign, station
    )


def summary(run, supported):
    rows = run["history"]
    assert any(r["native_set"] == supported for r in rows)
    checked = [r for r in rows if r["native_set"] <= supported]
    x = np.array([r["travel_mm"] for r in rows])
    f = np.array([r["cell_force_N"] for r in rows])
    assert np.all(np.diff(np.abs(x)) > 0)
    for i, r in enumerate(rows):
        r["within_parent_screens"] = r["native_set"] <= supported
        chosen = np.unique(np.r_[np.arange(0, i + 1, 2), i])
        r["alternate_station_actuator_work_mJ"] = float(np.trapezoid(f[chosen], x[chosen]))
        r["force_work_balance_error_mJ"] = r["summed_force_work_mJ"] - r["actuator_work_mJ"]
        r["contact_force_work_less_stiffness_energy_mJ"] = {
            k: r["work_by_group_mJ"][k] - r["stiffness_energy_change_mJ"][k]
            for k in r["contact_pilot_work_mJ"]
        }
    errors = [abs(r["force_work_balance_error_mJ"]) for r in checked]
    largest = max(r["actuator_work_mJ"] for r in checked)
    assert largest > 0 and max(errors) < 0.001 * largest + 2e-4
    for k in ("PLA", "shanks"):
        if k not in rows[0]["work_by_group_mJ"]:
            continue
        e = np.array([r["stiffness_energy_change_mJ"][k] for r in checked])
        w = np.array([r["work_by_group_mJ"][k] for r in checked])
        assert abs(w - e).max() < 0.02 * abs(e).max() + 2e-4
    run["max_supported_balance_residual_mJ"] = max(errors)
    run["supported_through_set"] = supported


def at_crossing(rows, target, key):
    """Trapezoidal work up to the first crossing, with a linear force-travel segment."""
    x = np.array([r["travel_mm"] for r in rows])
    f = np.array([r["cell_force_N"] for r in rows])
    values = f if key == "cell_force_N" else x
    sign = np.sign(values[-1])
    hits = np.flatnonzero(sign * (values - target) >= -1e-9)
    if not len(hits):
        return None
    i = int(hits[0])
    if abs(values[i] - target) < 1e-9:
        lo = i
        fraction = 0.0
    else:
        assert i > 0
        lo = i - 1
        fraction = (target - values[lo]) / (values[i] - values[lo])
    xat = x[lo] + fraction * (x[i] - x[lo])
    fat = f[lo] + fraction * (f[i] - f[lo])
    return {
        "native_sets": [rows[j]["native_set"] for j in (lo, i)],
        "travel_mm": xat,
        "force_N": fat,
        "external_work_mJ": float(rows[lo]["actuator_work_mJ"] + 0.5 * (fat + f[lo]) * (xat - x[lo])),
        "endpoint_work_bracket_mJ": [rows[j]["actuator_work_mJ"] for j in (lo, i)],
    }


def report(cased, bare, supported, *, comparison_stop=None):
    summary(cased, supported)
    summary(bare, bare["history"][-1]["native_set"])
    eligible = [r for r in cased["history"] if r["within_parent_screens"]]
    if comparison_stop is not None:
        assert comparison_stop <= supported
        cased["last_comparison_set"] = comparison_stop
        for row in cased["history"]:
            row["within_comparison_screens"] = row["within_parent_screens"] and row["native_set"] <= comparison_stop
        eligible = [r for r in eligible if r["within_comparison_screens"]]
    force = bare["history"][-1]["cell_force_N"]
    return {
        "cased": cased,
        "bare": bare,
        "at_bare_endpoint_force": at_crossing(eligible, force, "cell_force_N"),
        "bare_work_at_cased_stations": [
            at_crossing(bare["history"], r["travel_mm"], "travel_mm") for r in eligible
        ],
        "scope": "Post-lock quasi-static work from saved equilibria. The actuator curve uses signed X reaction and travel. "
        "Independent trapezoidal work uses every physical ENF slot, DPF translations and rotational DOFs, including "
        "both sides of each rigid-target contact. Net frictionless contact work includes numerical enforcement and "
        "finite step effects. Only PLA and the shanks are reported as recoverable elastic energy. "
        "The exterior-cell pull fixes the neighbouring cells. Subsequent stations beyond the stress or penetration "
        "screen are retained for numerical diagnosis only.",
    }


def run_checkpoint(folder):
    case = read(folder / "capture.json")["case"]
    cp = AUDIT / f"{case}_{folder.name}_checkpoint.json"
    proof = read(cp)
    campaign = proof["campaign"]
    assert proof["case"] == case and proof["rst_sha256"] == read(folder / "capture.json")["sha256"]
    first = next(i for i, row in enumerate(proof["states"]) if row["loadstep"] == 3) - 1
    cased = evaluate(folder, proof["rst_sha256"], case, campaign, proof["states"][first:])
    bare = closed_series(proof["bare_case"], campaign)
    assert bare["rst_sha256"] == proof["bare_rst_sha256"]
    record = report(cased, bare, proof["last_common_travel"]["cased"]["set"])
    record["checkpoint_sha256"] = digest(cp)
    reference = read(ROOT / "validation/pulls/raised_nylon_work.json")["work"][proof["bare_case"]]
    assert reference["rst_sha256"] == bare["rst_sha256"]
    assert abs(reference["native_POST1_work_mJ"] - bare["history"][-1]["actuator_work_mJ"]) < 1e-6
    write_json(AUDIT / f"{case}_{folder.name}_energy.json", record)


def archived(case, campaign, verdict, comparison):
    cased = closed_series(case, campaign, verdict)
    bare = closed_series(comparison["bare"], campaign)
    assert (
        cased["rst_sha256"] == comparison["native_rst_sha256"]
        and bare["rst_sha256"] == comparison["bare_rst_sha256"]
    )
    supported = comparison["equal_travel"]["cased"]["set"]
    parent = comparison.get("parent_screen_last_set", supported)
    record = report(cased, bare, parent, comparison_stop=supported if parent != supported else None)
    record["local_verdict_sha256"] = digest(verdict)
    matched = []
    for p in AUDIT.glob(case + "_ls*_energy.json"):
        previous = read(p)
        assert previous["checkpoint_sha256"] in {
            v["checkpoint_sha256"] for v in comparison["verified_checkpoints"]
        }
        assert len(previous["cased"]["history"]) <= len(cased["history"])
        for a, b in zip(previous["cased"]["history"], cased["history"]):
            assert (
                a["native_set"] == b["native_set"]
                and a["within_parent_screens"] == b["within_parent_screens"]
            )
            for k in ("actuator_work_mJ", "summed_force_work_mJ"):
                np.testing.assert_allclose(a[k], b[k], rtol=1e-7, atol=1e-6)
            for k in a["work_by_group_mJ"]:
                np.testing.assert_allclose(
                    a["work_by_group_mJ"][k], b["work_by_group_mJ"][k], rtol=1e-7, atol=1e-6
                )
        matched.append(digest(p))
    record["matched_checkpoint_sha256"] = matched
    dest = AUDIT / f"{case}_energy.json"
    write_json(dest, record)
    return dest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    run_checkpoint(parser.parse_args().folder.resolve())

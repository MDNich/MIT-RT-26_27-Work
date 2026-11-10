"""Measure contact-area, peak-pressure and force sensitivity at matched native pull stations."""

from hashlib import sha256

import numpy as np
from ansys.mapdl import reader
from audit_local import ROOT, read, table
from compare_pull import series
from film_identity import digest, verified, write_json
from snug_directional_result import first_bracket, paired
from snug_pocket_faces import SIX, at_integration_points
from snug_pull_pressure import contact_index, loaded_faces
from stage_snug_fit import AUDIT

METRICS = ("cell_force_N", "loaded_area_mm2", "normal_force_N", "peak_pressure_MPa")
GEOMETRY_CASE = "snug125_nylon_lateral_friction_locked_target4_m15"


def pressures(raw, index, k, expected):
    area = normal = peak = 0.0
    closed = points = 0
    total = np.zeros(3)
    signature = sha256()
    for element, native, stress, forces in loaded_faces(raw, index, k, signature):
        if element[2] != 861:
            continue
        assert len(forces) == 30 and element[12] == element[13] == element[16]
        slots = forces[:24].reshape(8, 3).astype(float)
        nodal = slots[SIX].copy()
        nodal[2] += slots[[3, 6]].sum(0)
        forces_at_points, _ = at_integration_points(nodal)
        np.testing.assert_allclose(-forces_at_points.sum(0), native[42:45], atol=1e-6, rtol=2e-6)
        active = stress[:3] > 0
        assert np.array_equal(active, native[:3] >= 2) and native[57] > 0
        area += float(native[57])
        normal += float(np.linalg.norm(forces_at_points[active], axis=1).sum())
        peak = max(peak, float(max(stress[:3])))
        points += int(active.sum())
        closed += 1
        total += native[42:45]
    assert closed == expected["closed_faces"]
    np.testing.assert_allclose(total, expected["force_N"], atol=1e-6, rtol=2e-6)
    return {
        "loaded_area_mm2": area,
        "peak_pressure_MPa": peak,
        "normal_force_N": normal,
        "patch_mean_MPa": normal / area if area else None,
        "loaded_faces": closed,
        "loaded_points": points,
        "moving_contact_reaction_N": total.tolist(),
        "native_pressure_records_sha256": signature.hexdigest(),
    }


def history(case, folder, sha, comparison, verdict):
    verified(folder / "pull.rst", comparison["native_rst_sha256"])
    verified(folder / "case_pairs.csv", sha["case_pairs.csv"])
    verified(folder / "model.inp", sha["model.inp"])
    pairs = {int(r["set"]): r for r in table(folder / "case_pairs.csv") if r["pair"] == 861}
    support = comparison["equal_travel"]
    last = support["cased"]["set"] if support else 0
    proof, stations = series(case, proof_path=verdict)
    assert proof["rst_sha256"] == comparison["native_rst_sha256"] == sha["pull.rst"]
    raw = reader.read_binary(folder / "pull.rst")
    index = contact_index(raw)
    states = []
    for s in stations:
        k = s["set"]
        if k > last:
            break
        row = pairs[k]
        metrics = pressures(
            raw, index, k, {"closed_faces": row["closed"], "force_N": [row["f" + q + "_N"] for q in "xyz"]}
        )
        states.append(dict(set=k, ux_mm=s["ux_mm"], cell_force_N=s["cell_force_N"], **metrics))
    return {
        "case": case,
        "rst_sha256": sha["pull.rst"],
        "input_sha256": sha["model.inp"],
        "verdict_sha256": digest(verdict),
        "material_sha256": comparison["print_material_sha256"],
        "last_supported_native_set": last,
        "source": comparison["source"],
        "bare_rst_sha256": comparison["bare_rst_sha256"],
        "bare_endpoint_load_N": comparison["bare_endpoint_load_N"],
        "states": states,
    }


def matched(first, second):
    """Only compare pressures at actual common travel stations. At a force crossing retain both native bounds."""
    assert first["source"] == second["source"] and first["bare_rst_sha256"] == second["bare_rst_sha256"]
    load = first["bare_endpoint_load_N"]
    assert load == second["bare_endpoint_load_N"]
    sign = -1 if first["source"].endswith("_minus") else 1
    ranges, by_force = [], []
    for branch in (first, second):
        states = branch["states"]
        x = sign * np.array([s["ux_mm"] for s in states])
        assert (np.diff(x) > 0).all()
        ranges.append(x)
        bracket = first_bracket(states, "cell_force_N", load, sign)
        if bracket:
            by_id = {s["set"]: s for s in states}
            by_force.append([by_id[k] for k in bracket["native_sets"]])
        else:
            by_force.append(None)
    common = []
    for a, x in zip(first["states"], ranges[0], strict=True):
        pos = np.flatnonzero(abs(ranges[1] - x) < 1e-8)
        if len(pos) and x > 1e-8:
            assert len(pos) == 1
            b = second["states"][pos[0]]
            common.append(
                dict(
                    travel_mm=[a["ux_mm"], b["ux_mm"]],
                    native_sets=[a["set"], b["set"]],
                    **{m: [a[m], b[m]] for m in METRICS},
                )
            )
    return {
        "cases": [first["case"], second["case"]],
        "sources": [first["rst_sha256"], second["rst_sha256"]],
        "common_native_travel": common,
        "signed_bare_endpoint_N": load,
        "surrounding_force_states": by_force,
        "scope": "Exact shared saved travel within 1e-8 mm on independently screened paths. The endpoint "
        "force comparison retains each run's two saved states without interpolating contact pressure.",
    }


def check_checkpoint():
    from snug_local_checkpoint import CASE
    from snug_pull_target_geometry import BASE

    proof = read(AUDIT / f"{BASE}_cell_pressure.json")
    folder = ROOT / ".runtime/qa/snug125/forward-readback/ls3_ss24"
    source = read(AUDIT / f"{CASE}_{folder.name}_checkpoint.json")
    verified(folder / "pull.rst", source["rst_sha256"])
    assert source["rst_sha256"] == proof["later_rst_crosscheck_sha256"]
    raw = reader.read_binary(folder / "pull.rst")
    index = contact_index(raw)
    states = []
    for s in proof["states"]:
        k = s["native_set"]
        native = source["states"][k - 1]
        got = pressures(raw, index, k, native["both_contact_pairs"]["861"])
        assert got["native_pressure_records_sha256"] == s["native_pressure_records_sha256"]
        known = s["cells"].get("4", {})
        for key, field in [
            ("loaded_area_mm2", "contact_area_mm2"),
            ("normal_force_N", "normal_load_N"),
            ("peak_pressure_MPa", "peak_pressure_MPa"),
        ]:
            np.testing.assert_allclose(got[key], known.get(field, 0.0), rtol=2e-7, atol=1e-7)
        states.append(dict(set=k, ux_mm=s["travel_mm"], cell_force_N=s["actuator_N"], **got))
    reference = {
        "case": CASE,
        "source": "lateral_friction_locked",
        "bare_rst_sha256": source["bare_rst_sha256"],
        "rst_sha256": source["rst_sha256"],
        "bare_endpoint_load_N": source["equal_bare_endpoint_load"]["bare"]["cell_force_N"],
        "states": states,
    }
    replay = matched(reference, reference)
    assert len(replay["common_native_travel"]) == len(states)
    assert [v["set"] for v in replay["surrounding_force_states"][0]] == [13, 14]
    print("Verified left-cell areas, normal loads and peaks at", len(states), "native stations.")


def closed(case, folder, sha, comparison, verdict, *, reference=None):
    output = AUDIT / f"{case}_moving_contact.json"
    result = history(case, folder, sha, comparison, verdict)
    write_json(output, result)
    if reference is not None:
        mate = AUDIT / f"{reference}_moving_contact.json"
        (v,) = [
            p
            for kind in ("local", "partial_local")
            if (p := ROOT / "validation" / kind / f"{reference}.json").is_file()
        ]
        parent = read(v)
        base = (
            read(AUDIT / "local_inputs_m15.json").get(reference)
            or read(AUDIT / "local_pull_step_input.json")[reference]
        )
        parent_folder = ROOT / ".runtime/archive" / parent["campaign"] / reference
        ledger = read(ROOT / ".runtime/receipts" / parent["campaign"] / reference / "archived.json")
        hashes = {f["name"]: f["sha256"] for f in ledger["files"]}
        assert hashes["model.inp"] == base["input_sha256"] and hashes["pull.rst"] == parent["rst_sha256"]
        parent_comparison = paired(reference, base["bare_reference"], v)
        support = parent_comparison["equal_travel"]
        last = support["cased"]["set"] if support else 0
        if not mate.is_file():
            write_json(mate, history(reference, parent_folder, hashes, parent_comparison, v))
        a = read(mate)
        assert (
            a["case"] == reference
            and a["rst_sha256"] == hashes["pull.rst"]
            and a["input_sha256"] == hashes["model.inp"]
        )
        assert a["verdict_sha256"] == digest(v) and a["last_supported_native_set"] == last
        assert a["material_sha256"] == parent_comparison["print_material_sha256"]
        comparison_path = AUDIT / f"{case}_contact_resolution.json"
        write_json(
            comparison_path,
            dict(
                reference_history_sha256=digest(mate),
                candidate_history_sha256=digest(output),
                **matched(a, result),
            ),
        )
    return output


if __name__ == "__main__":
    check_checkpoint()

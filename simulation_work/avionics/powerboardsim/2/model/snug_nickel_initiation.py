"""Check the ductile initiation integral against MAPDL and evaluate the nickel histories at matched loads."""

import argparse

import numpy as np
from ansys.mapdl import reader
from ansys.mapdl.reader.rst import ELEMENT_INDEX_TABLE_KEYS
from audit_local import ROOT, read, table
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_damage_family import law, result_file
from snug_local_checkpoint import CAMPAIGN, CASE
from stage_snug_fit import AUDIT, INPUTS

SECTIONS = ("bottom", "top", "middle")
CASES = (
    "bare_damage_coupon_uniform",
    "bare_damage_cont_nominal",
    "stand3_nylon_damage_cont_nominal_pin1",
    "stand3_aluminium_damage_cont_nominal_pin1",
)


def tables():
    manifest = AUDIT / "damage_family_inputs.json"
    grid = read(manifest)["cases"]["bare"]
    curves = {}
    for entry in grid.values():
        if entry["control"] != "material_grid":
            continue
        path = INPUTS / entry["case"] / "model.inp"
        verified(path, entry["input_sha256"])
        (points, uf), _ = law(path.read_bytes())
        key = entry["eps0"]
        assert uf == entry["evolution_length_mm"] and key == points[2, 1]
        if key in curves:
            np.testing.assert_array_equal(curves[key], points)
        curves[key] = points
    assert sorted(curves) == [0.1, 0.3, 0.6]
    return curves


def shell_state(raw, index, order, damage):
    """Read the twelve saved sites per shell from the original SMP elemental records."""
    offsets, _, base = raw._element_solution_header(index)
    assert np.all(offsets[order] > 0)
    en = np.empty((len(order), 3, 4, 10))
    source = np.empty((len(order), 3, 4, 7)) if damage else None
    tensor = None if damage else np.empty((len(order), 3, 4, 6))
    tensor_slot = ELEMENT_INDEX_TABLE_KEYS.index("ENS")
    en_slot = ELEMENT_INDEX_TABLE_KEYS.index("ENL")
    mnl_slot = ELEMENT_INDEX_TABLE_KEYS.index("MNL")
    for j, offset in enumerate(base + offsets[order]):
        pos = int(offset)
        keys = raw.read_record(pos)
        assert keys[en_slot] > 0
        en[j] = raw.read_record(pos + int(keys[en_slot])).reshape(3, 4, 10)
        if tensor is not None:
            assert keys[tensor_slot] > 0
            tensor[j] = raw.read_record(pos + int(keys[tensor_slot])).reshape(3, 4, 6)
        if damage:
            assert keys[mnl_slot] > 0
            mnl = raw.read_record(pos + int(keys[mnl_slot]))
            # The material block directory stores a type, length and one-based start per entry.
            n = int(mnl[0])
            header = mnl[1 : 1 + 3 * n].reshape(n, 3)
            assert np.array_equal(header, header.astype(int))
            selected = header[header[:, 0] == 64]
            assert selected.shape == (1, 3) and selected[0, 1] == 84
            start = int(selected[0, 2]) - 1
            assert start >= 1 + 3 * n and start + 84 <= len(mnl)
            source[j] = mnl[start : start + 84].reshape(3, 4, 7)
    assert np.isfinite(en).all()
    return en, source, tensor


def site(criterion):
    i, j, k = np.unravel_index(np.argmax(criterion), criterion.shape)
    return {
        "maximum": float(criterion[i, j, k]),
        "nickel_element": int(i + 1),
        "section": SECTIONS[j],
        "corner": int(k + 1),
    }


def integrate(raw, n_shell, sets, curves, travel, force, *, native=None, native_eps=None, maps=None):
    elements = np.arange(1, n_shell + 1)
    idx = np.argsort(raw._eeqv)
    order = idx[positions(raw._eeqv[idx], elements)]
    grid = raw.grid.cell_data
    shell = np.sort(grid["ansys_elem_num"][grid["ansys_elem_type_num"] == 181])
    np.testing.assert_array_equal(shell, elements)
    assert np.array_equal(sets, np.arange(1, len(sets) + 1))
    assert np.all(raw._resultheader["ls_table"][sets - 1, 1] != 999999)
    old = np.zeros((n_shell, 3, 4))
    accum = {key: old.copy() for key in curves}
    tensor_sum = old.copy()
    max_tensor_difference = 0.0
    checks = {
        "replayed_criterion": 0.0,
        "accumulated_strain": 0.0,
        "POST1_section_damage": 0.0,
        "POST1_peak_plastic_strain": 0.0,
        "negative_plastic_increment": 0.0,
        "decrease_in_native_criterion": 0.0,
        "native_threshold_at_finite_damage": 0.0,
    }
    rows = []
    direct_before = old.copy()
    for rst_set, ux, fx in zip(sets, travel, force, strict=True):
        k = int(rst_set - 1)
        en, mnl, tensor = shell_state(raw, k, order, native is not None)
        p = en[..., 3]
        inc = p - old
        checks["negative_plastic_increment"] = max(
            checks["negative_plastic_increment"], float(-inc.min())
        )
        assert inc.min() >= -5e-6
        nominal_d = 0 if mnl is None else mnl[..., 0]
        # Active plastic flow gives von Mises effective stress equal to the current flow stress.
        # Mean nominal stress and nominal von Mises stress have the same scalar damage factor.
        denom = en[..., 0] * (1 - nominal_d)
        flowing = inc > 0
        assert np.all(denom[flowing] > 0)
        triax = np.divide(en[..., 2], denom, out=np.zeros_like(p), where=flowing)
        for key, t in curves.items():
            threshold = np.interp(triax, t[:, 0], t[:, 1])
            accum[key] += np.maximum(inc, 0) / threshold
        row = {
            "native_set": int(rst_set),
            "travel_mm": float(ux),
            "force_N": float(fx),
            "curves": {str(key): site(values) for key, values in accum.items()},
        }
        if tensor is not None:
            x, y, z, xy, yz, xz = np.moveaxis(tensor, -1, 0)
            vm = np.sqrt(
                0.5 * ((x - y) ** 2 + (y - z) ** 2 + (z - x) ** 2) + 3 * (xy**2 + yz**2 + xz**2)
            )
            assert np.all(vm[flowing] > 0)
            tensor_triax = np.divide((x + y + z) / 3, vm, out=np.zeros_like(p), where=flowing)
            baseline = curves[0.3]
            tensor_sum += np.maximum(inc, 0) / np.interp(tensor_triax, baseline[:, 0], baseline[:, 1])
            row["nominal_maximum_using_stress_tensor"] = float(tensor_sum.max())
            max_tensor_difference = max(
                max_tensor_difference, abs(float(tensor_sum.max() - accum[0.3].max()))
            )
        if mnl is not None:
            assert (
                np.isfinite(mnl).all() and mnl[..., 0].min() >= -1e-8 and mnl[..., 0].max() <= 1.000001
            )
            direct = mnl[..., 6]
            assert direct.min() >= -1e-6 and direct.max() <= 1.000001
            checks["decrease_in_native_criterion"] = max(
                checks["decrease_in_native_criterion"], float((direct_before - direct).max())
            )
            checks["accumulated_strain"] = max(
                checks["accumulated_strain"], float(np.max(abs(p - mnl[..., 1])))
            )
            err = np.abs(np.minimum(1, accum[native_eps]) - direct)
            checks["replayed_criterion"] = max(checks["replayed_criterion"], float(err.max()))
            active = nominal_d > 1e-8
            if active.any():
                checks["native_threshold_at_finite_damage"] = max(
                    checks["native_threshold_at_finite_damage"], float(abs(direct[active] - 1).max())
                )
            sections = nominal_d.mean(2)
            checks["POST1_section_damage"] = max(
                checks["POST1_section_damage"], abs(float(sections.max() - native[k]["damage"]))
            )
            checks["POST1_peak_plastic_strain"] = max(
                checks["POST1_peak_plastic_strain"], abs(float(p.mean(2).max() - native[k]["plastic"]))
            )
            if maps and int(rst_set) in maps:
                file, sha = maps[int(rst_set)]
                verified(file, sha)
                native_map = table(file)
                np.testing.assert_array_equal(native_map["element"], elements)
                extracted = np.column_stack(
                    [native_map["damage_bot"], native_map["damage_top"], native_map["damage_mid"]]
                )
                checks["POST1_section_damage"] = max(
                    checks["POST1_section_damage"], float(abs(sections - extracted).max())
                )
            row.update(
                native_criterion=site(direct),
                maximum_stored_point_damage=float(nominal_d.max()),
                maximum_native_section_damage=float(sections.max()),
            )
            direct_before = direct.copy()
        old = p.copy()
        rows.append(row)
    if native is not None:
        assert checks["POST1_section_damage"] < 3e-7 and checks["POST1_peak_plastic_strain"] < 3e-6, (
            checks
        )
        assert (
            checks["accumulated_strain"] < 5e-6 and checks["native_threshold_at_finite_damage"] < 2e-5
        ), checks
    if native is None:
        checks["maximum_nominal_peak_change_using_stress_tensor"] = max_tensor_difference
    return rows, checks


def control(case, curves):
    verdict = result_file(case)
    assert verdict is not None
    meta = read(verdict)
    campaign = meta["campaign"]
    assert campaign == CAMPAIGN and meta["case"] == case
    receipt = ROOT / ".runtime/receipts" / campaign / case
    ledger = read(receipt / "archived.json")
    assert (
        ledger["case"] == case
        and ledger["campaign"] == campaign
        and (receipt / "released.txt").is_file()
    )
    sha = {r["name"]: r["sha256"] for r in ledger["files"]}
    folder = ROOT / ".runtime/archive" / campaign / case
    for name in ("tear.rst", "local_job.json", "model.inp"):
        verified(folder / name, sha[name])
    spec = read(folder / "local_job.json")
    assert (
        spec["case"] == case
        and spec["files"]["model.inp"] == sha["model.inp"]
        and sha["tear.rst"] == meta["rst_sha256"]
    )
    ((points, _), _) = law((folder / "model.inp").read_bytes())
    eps = float(points[2, 1])
    np.testing.assert_array_equal(curves[eps], points)
    coupon = spec["coupon"]
    raw = reader.read_binary(str(folder / "tear.rst"))
    sets = np.flatnonzero(raw._resultheader["ls_table"][:, 1] != 999999) + 1
    file = "accepted_history.csv" if coupon else "set_inventory.csv"
    verified(folder / file, sha[file])
    native = table(folder / file)
    np.testing.assert_array_equal(native["set"], sets)
    np.testing.assert_allclose(native["time"], raw.time_values[sets - 1], rtol=0, atol=1e-7)
    limit_source = None
    if spec["cased"]:
        limit_file = ROOT / "validation/pulls" / (case + "_damage_scope.json")
        lim = read(limit_file)
        assert lim["case"] == case and lim["fixture_audit_sha256"] == digest(verdict)
        if lim["last_station_before_limits"] is None:
            return None
        sets = sets[: lim["last_station_before_limits"]["native_set"]]
        limit_source = digest(limit_file)
    native = native[: len(sets)]
    n_shell = 1
    maps = {}
    if not coupon:
        cfg = ROOT / ".runtime/local_inputs" / spec["source"] / "mesh.json"
        verified(cfg, read(ROOT / "validation/local_inputs.json")[spec["source"]]["files"]["mesh.json"])
        n_shell = len(read(cfg)["elements"])
        verified(folder / "history.csv", sha["history.csv"])
        for row in table(folder / "history.csv"):
            where = np.flatnonzero(np.isclose(native["time"], row["time"], rtol=0, atol=1e-7))
            if len(where):
                (i,) = where
                name = f"damage_{int(row['step'])}.csv"
                maps[int(sets[i])] = (folder / name, sha[name])
    reported = [
        {"damage": float(r["damage"]), "plastic": float(r["eppl" if coupon else "peeq"])}
        for r in native
    ]
    rows, checks = integrate(
        raw,
        n_shell,
        sets,
        curves,
        native["ux_mm"],
        native["fx_N"],
        native=reported,
        native_eps=eps,
        maps=maps,
    )
    verified_replay = max(checks["replayed_criterion"], checks["decrease_in_native_criterion"]) < 1e-4
    first = next((j for j, r in enumerate(rows) if r["maximum_stored_point_damage"] > 0), len(rows))
    # Changing a material card allows reusing only the path preceding the first damage on either law.
    brackets = {}
    for key in curves:
        if not verified_replay:
            break
        end = first + 1 if first < len(rows) and key == eps else first
        for j in range(end):
            if rows[j]["curves"][str(key)]["maximum"] >= 1:
                brackets[str(key)] = [
                    (r["native_set"], r["travel_mm"], r["force_N"]) for r in rows[max(0, j - 1) : j + 1]
                ]
                break
    return {
        "case": case,
        "campaign": campaign,
        "verdict_sha256": digest(verdict),
        "rst_sha256": sha["tear.rst"],
        "input_sha256": sha["model.inp"],
        "POST1_sha256": sha[file],
        "assembled_result_sets": raw.nsets,
        "converged_sets_before_scope": len(sets),
        "excluded_diagnostic_sets": int((raw._resultheader["ls_table"][:, 1] == 999999).sum()),
        "stored_sites_per_set": n_shell * 12,
        "source_initiation_card": eps,
        "matched_element_maps": len(maps),
        "native_limit_record_sha256": limit_source,
        "first_stored_point_damage_set": rows[first]["native_set"] if first < len(rows) else None,
        "field_replay_verified": verified_replay,
        "checks": checks,
        "first_replayed_initiation_before_stored_damage": brackets,
        "first_native_point_damage_bracket": rows[max(0, first - 1) : first + 1]
        if first < len(rows)
        else None,
        "native_trace_columns": [
            "set",
            "travel_mm",
            "force_N",
            "maximum_initiation_criterion",
            "maximum_section_damage",
        ],
        "native_trace": [
            [
                r["native_set"],
                r["travel_mm"],
                r["force_N"],
                r["native_criterion"]["maximum"],
                r["maximum_native_section_damage"],
            ]
            for r in rows
        ],
    }


def bilinear(curves):
    folder = ROOT / ".runtime/qa/snug125/forward-readback/ls3_ss24"
    checkpoint = AUDIT / (CASE + "_ls3_ss24_checkpoint.json")
    sub = AUDIT / "nylon_forward_tab_submodel.json"
    cp = read(checkpoint)
    ref = read(sub)
    assert (
        ref["checkpoint_sha256"] == digest(checkpoint) and cp["rst_sha256"] == ref["DPF_source_sha256"]
    )
    verified(folder / "pull.rst", cp["rst_sha256"])
    finest = [
        e["first_sample_above_coupon_native_set"] for e in ref["independent"] if e["subdivisions"] == 8
    ]
    assert len(finest) >= 2 and len(set(finest)) == 1
    stop = min(cp["first_excluded_set"], min(finest)) - 1
    snug_rows = cp["states"][:stop]
    raw = reader.read_binary(str(folder / "pull.rst"))
    mesh = ROOT / ".runtime/local_inputs/lateral_friction_locked/mesh.json"
    verified(
        mesh,
        read(ROOT / "validation/local_inputs.json")["lateral_friction_locked"]["files"]["mesh.json"],
    )
    n = len(read(mesh)["elements"])
    assert n == 2304 and all(r["within_screens"] for r in snug_rows)
    snug, snug_check = integrate(
        raw,
        n,
        np.arange(1, stop + 1),
        curves,
        [r["travel_mm"] for r in snug_rows],
        [r["cell_force_N"] for r in snug_rows],
    )
    case = cp["bare_case"]
    archive = ROOT / ".runtime/archive" / CAMPAIGN / case
    rec = ROOT / ".runtime/receipts" / CAMPAIGN / case
    ledger = read(rec / "archived.json")
    assert (
        ledger["case"] == case and ledger["campaign"] == CAMPAIGN and (rec / "released.txt").is_file()
    )
    hashes = {r["name"]: r["sha256"] for r in ledger["files"]}
    assert hashes["pull.rst"] == cp["bare_rst_sha256"]
    for f in ("pull.rst", "history.csv"):
        verified(archive / f, hashes[f])
    raw = reader.read_binary(str(archive / "pull.rst"))
    h = table(archive / "history.csv")
    np.testing.assert_array_equal(h["set"], np.arange(1, raw.nsets + 1))
    np.testing.assert_allclose(h["time"], raw.time_values, rtol=0, atol=1e-7)
    bare, bare_check = integrate(raw, n, h["set"].astype(int), curves, h["ux_mm"], h["fx_N"])
    bracket = cp["equal_bare_endpoint_load"]["cased"]["native_sets"]
    assert cp["equal_bare_endpoint_load"]["bare"]["set"] == bare[-1]["native_set"]
    low = next(i for i, r in enumerate(bare) if r["travel_mm"] >= snug[-1]["travel_mm"]) - 1
    assert low >= 0 and bracket[-1] <= stop
    return {
        "positive_pull_checkpoint_sha256": digest(checkpoint),
        "bilinear_checks": {"snug": snug_check, "bare": bare_check},
        "submodel_sha256": digest(sub),
        "bare_rst_sha256": hashes["pull.rst"],
        "snug_rst_sha256": cp["rst_sha256"],
        "bare_history_sha256": hashes["history.csv"],
        "last_before_refined_PLA_crossing": snug[-1]["native_set"],
        "common_load_N": bare[-1]["force_N"],
        "bare_common_load_set": bare[-1]["native_set"],
        "snug_common_load_bracket": bracket,
        "bare_bracket_at_last_snug_travel": [bare[low]["native_set"], bare[low + 1]["native_set"]],
        "bare": bare,
        "snug": snug,
        "scope": "Independent initiation integral on the bilinear nickel histories. The separate ductile material law has no feedback on these saved fields.",
    }


def run():
    curves = tables()
    controls = {}
    for case in CASES:
        result = control(case, curves)
        assert result and result["field_replay_verified"] and result["converged_sets_before_scope"] > 0
        if case == "bare_damage_cont_nominal":
            original = read(result_file(case))["damage_onset_bracket"]
            assert [r["native_set"] for r in original] == [
                r["native_set"] for r in result["first_native_point_damage_bracket"]
            ]
            assert result["matched_element_maps"] == 101
        if case != "bare_damage_cont_nominal":
            del result["native_trace_columns"], result["native_trace"]
        print(
            case, result["checks"], result["first_replayed_initiation_before_stored_damage"], flush=True
        )
        controls[case] = result
    result = bilinear(curves)
    write_json(
        AUDIT / "nickel_initiation_replay.json",
        {
            "native_material_controls": controls,
            "family_inputs_sha256": digest(AUDIT / "damage_family_inputs.json"),
            "matched_bilinear": result,
            "method": "Right-endpoint plastic-strain increments divided by the tabulated critical strain at the current triaxiality. "
            "The three stored shell sections have four output sites each. The 1.0 criterion marks the start of softening.",
        },
    )
    print("Final screened snug station", result["snug"][-1], flush=True)


def closed_family_case(case):
    """Collect the direct material response of each actual, scoped bare or snug variant."""
    registry = AUDIT / "damage_family_inputs.json"
    family = read(registry)
    entry = next(
        (
            spec
            for branch in family["cases"].values()
            for spec in branch.values()
            if spec["case"] == case
        ),
        None,
    )
    if entry is None or result_file(case) is None:
        return
    result = control(case, tables())
    if result is None:
        return
    assert (
        result["input_sha256"] == entry["input_sha256"]
        and result["stored_sites_per_set"] == 12 * entry["nickel_shell_elements"]
    )
    result["family_inputs_sha256"] = digest(registry)
    if case.startswith("bare_") and entry["control"] == "material_grid":
        replay = AUDIT / "nickel_initiation_replay.json"
        if replay.exists():
            nominal = read(replay)["native_material_controls"]["bare_damage_cont_nominal"]
            expected = nominal["first_replayed_initiation_before_stored_damage"].get(str(entry["eps0"]))
            result["nominal_history_comparison"] = {
                "nominal_replay_sha256": digest(replay),
                "expected_first_initiation_bracket": expected,
                "conditional_on": "The assemblies share the pre-damage solution. A higher-threshold variant can continue past damage on the nominal path.",
            }
    write_json(AUDIT / (case + "_nickel_initiation.json"), result)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--native-case",
        help="Audit a closed snug damage fixture against its own material and contact scope",
    )
    args = p.parse_args()
    if args.native_case:
        closed_family_case(args.native_case)
    else:
        run()

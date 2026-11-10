"""Reconstruct post-initiation nickel damage from native strain histories and the deformed SHELL181 midsurface."""

import argparse
import re
from hashlib import sha256

import numpy as np
from ansys.mapdl import reader
from audit_local import ROOT, read, table
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_damage_family import law, result_file
from snug_nickel_initiation import SECTIONS, shell_state
from stage_snug_fit import AUDIT
from tab_seating import read_point_file

CONTROLS = (
    "bare_damage_coupon_uniform",
    "bare_damage_coupon_unsym",
    "bare_damage_coupon_nominal_v4",
    "bare_damage_cont_nominal",
)
CORNERS = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]])


def characteristic_lengths(xyz, points):
    """Length from the current in-plane area at each integration site, in mm."""
    cross = np.cross(xyz[:, 2] - xyz[:, 0], xyz[:, 3] - xyz[:, 1])
    twice_area = np.linalg.norm(cross, axis=1)
    assert np.all(twice_area > 0)
    normal = cross / twice_area[:, None]
    average = np.sqrt(0.5 * twice_area / points)
    if points == 1:
        return np.broadcast_to(average[:, None], (len(average), 4)), average
    assert points == 4
    result = []
    for r, s in CORNERS / np.sqrt(3):
        dr = CORNERS[:, 0] * (1 + CORNERS[:, 1] * s) / 4
        ds = CORNERS[:, 1] * (1 + CORNERS[:, 0] * r) / 4
        det = np.einsum("ij,ij->i", np.cross(dr @ xyz, ds @ xyz), normal)
        assert np.all(det > 0)
        result.append(np.sqrt(det))
    lengths = np.stack(result, axis=1)
    np.testing.assert_allclose((lengths**2).sum(1), twice_area / 2, rtol=1e-11, atol=1e-14)
    return lengths, average


def audit(case):
    verdict = result_file(case)
    assert verdict is not None
    meta = read(verdict)
    campaign = meta["campaign"]
    receipt = ROOT / ".runtime/receipts" / campaign / case
    folder = ROOT / ".runtime/archive" / campaign / case
    ledger = read(receipt / "archived.json")
    assert (
        ledger["case"] == case == meta["case"]
        and ledger["campaign"] == campaign
        and (receipt / "released.txt").is_file()
    )
    sha = {f["name"]: f["sha256"] for f in ledger["files"]}
    for name in ("model.inp", "local_job.json", "tear.rst"):
        verified(folder / name, sha[name])
    job = read(folder / "local_job.json")
    assert (
        job["case"] == case
        and job["job"] == "tear"
        and sha["model.inp"] == job["files"]["model.inp"]
        and meta["rst_sha256"] == sha["tear.rst"]
    )
    deck = (folder / "model.inp").read_bytes()
    (_, uf), _ = law(deck)
    assert b"ET,1,SHELL181" in deck.upper() and b"SECDATA,.15,1,0,7" in deck and b"NLGEOM,ON" in deck.upper()
    (key,) = re.findall(rb"(?im)^KEYOPT,1,3,([02])\s*$", deck)
    nip = 1 if key == b"0" else 4
    (cap,) = re.findall(rb"(?im)^TB,CDM,1,,,DCAP\s*\nTBDATA,1,([^\s,]+)", deck)
    cap = float(cap)
    assert 0 < cap <= 1 and not re.search(rb"(?im)^TB,CDM,[^\n]+(?:VREG|EXPD)", deck)
    raw = reader.read_binary(folder / "tear.rst")
    physical = raw._resultheader["ls_table"][:, 1] != 999999
    name = "accepted_history.csv" if job["coupon"] else "set_inventory.csv"
    verified(folder / name, sha[name])
    history = table(folder / name)
    np.testing.assert_array_equal(history["set"], np.flatnonzero(physical) + 1)
    np.testing.assert_allclose(history["time"], raw.time_values[physical], atol=1e-7, rtol=0)
    scope_sha = None
    if job["cased"]:
        scope = ROOT / "validation/pulls" / f"{case}_damage_scope.json"
        lim = read(scope)
        assert lim["fixture_audit_sha256"] == digest(verdict) and lim["case"] == case
        scope_sha = digest(scope)
        stop = lim["last_station_before_limits"]
        history = history[history["set"] <= (stop["native_set"] if stop else 0)]
    grid = raw.grid.cell_data
    elements = np.sort(grid["ansys_elem_num"][grid["ansys_elem_type_num"] == 181])
    np.testing.assert_array_equal(elements, np.arange(1, len(elements) + 1))
    order = np.argsort(raw._eeqv)
    rows = order[positions(raw._eeqv[order], elements)]
    conn = np.stack([raw.mesh.elem[ix][10:14] for ix in rows])
    assert (np.diff(np.sort(conn, axis=1), axis=1) > 0).all()
    mesh_sha = None
    regions = None
    if not job["coupon"]:
        mesh_path = ROOT / ".runtime/local_inputs" / job["source"] / "mesh.json"
        mesh_sha = read(ROOT / "validation/local_inputs.json")[job["source"]]["files"]["mesh.json"]
        verified(mesh_path, mesh_sha)
        mesh = read(mesh_path)
        np.testing.assert_array_equal(conn, mesh["elements"])
        regions = np.array(mesh["region"])
    assert np.isfinite(history["damage"]).all() and (history["damage"] >= 0).all()
    active = {}
    summary = []
    first = None
    half = None
    previous = None
    for h in history:
        k = int(h["set"])
        state = {
            "set": k,
            "travel_mm": float(h["ux_mm"]),
            "force_N": float(h["fx_N"]),
            "native_max_section_damage": float(h["damage"]),
        }
        # All site damage values are nonnegative. The published POST1 value is the maximum four-site mean.
        if h["damage"] > 0:
            _, m, _ = shell_state(raw, k - 1, rows, True)
            D = m[..., 0]
            if nip == 1:
                for col in (0, 1, 5, 6):
                    np.testing.assert_allclose(
                        m[:, :, 1:, col], np.repeat(m[:, :, :1, col], 3, axis=2), rtol=0, atol=1e-7
                    )
            assert D.min() >= -1e-8 and D.max() <= cap + 1e-6
            np.testing.assert_allclose(D.mean(2).max(), h["damage"], atol=3e-7, rtol=1e-6)
            e, section, point = np.nonzero(D > 0)
            idx = (e, section, point)
            assert np.all(abs(m[..., 6][idx] - 1) < 2e-6)
            dp = m[..., 1][idx] - m[..., 5][idx]
            assert dp.min() > -1e-7
            active[k] = (e, section, point, D[idx], np.maximum(0.0, dp))
            peak = int(D[idx].argmax())
            state.update(
                native_max_point_damage=float(D[idx][peak]),
                damaged_sites=len(e),
                distinct_in_plane_sites_across_saved_sections=len(e) * nip // 4,
                damaged_elements=len(np.unique(e)),
                damaged_sites_by_section=np.bincount(section, minlength=3).tolist(),
                sites_above_reporting_threshold=int(np.count_nonzero(D > 1e-4)),
                peak_element=int(elements[e[peak]]),
                peak_section=SECTIONS[section[peak]],
                peak_corner=int(point[peak]) + 1,
                post_onset_plastic_strain_at_peak=float(dp[peak]),
                onset_plastic_strain_at_peak=float(m[..., 5][idx][peak]),
            )
            if regions is not None and k == int(history[-1]["set"]):
                state["affected_element_regions"] = {str(elements[i]): str(regions[i]) for i in np.unique(e)}
            if first is None:
                first = [previous, state] if previous else [state]
            if half is None and state["native_max_point_damage"] >= 0.5:
                half = [previous, state] if previous else [state]
        else:
            if k == int(history[-1]["set"]):
                _, m, _ = shell_state(raw, k - 1, rows, True)
                np.testing.assert_allclose(m[..., 0], 0, atol=1e-10, rtol=0)
            state.update(
                native_max_point_damage=0.0,
                damaged_sites=0,
                distinct_in_plane_sites_across_saved_sections=0,
                damaged_elements=0,
            )
        summary.append(state)
        previous = state
    errs = {"current_point_length": 0.0, "current_mean_length": 0.0, "undeformed_point_length": 0.0}
    cached = None
    if active:
        sets = list(active)
        used = np.unique(np.concatenate([a[0] for a in active.values()]))
        node = np.unique(conn[used])
        X = raw.mesh.nodes[positions(raw.mesh.nnum, node)]
        local = positions(node, conn[used])
        request_id = sha256(np.asarray(sets + [0] + node.tolist(), dtype="<i8").tobytes()).hexdigest()[:16]
        out = ROOT / ".runtime/post" / campaign / case / ("damage_evolution_" + request_id)
        u, _ = read_point_file(folder / "tear.rst", out, sha["tear.rst"], sets, node.tolist())
        cached = digest(out / "displacements.bin")
        initial, _ = characteristic_lengths(X[local], nip)
        by_set = {s["set"]: s for s in summary}
        for k, d in zip(sets, u, strict=True):
            e, section, point, D, dp = active[k]
            at = positions(used, e)
            length, mean = characteristic_lengths((X + d)[local], nip)
            width = dp * length[at, point]
            pred = np.minimum(cap, width / uf)
            for key, val in [
                ("current_point_length", pred),
                ("current_mean_length", np.minimum(cap, dp * mean[at] / uf)),
                ("undeformed_point_length", np.minimum(cap, dp * initial[at, point] / uf)),
            ]:
                errs[key] = max(errs[key], float(abs(val - D).max()))
            imax = int(D.argmax())
            state = by_set[k]
            state.update(
                peak_location_length_mm=float(length[at[imax], point[imax]]),
                peak_location_post_onset_displacement_mm=float(width[imax]),
                reconstructed_max_point_damage=float(pred.max()),
            )
            if job["coupon"]:
                np.testing.assert_allclose(d[positions(node, [2, 3]), 0], state["travel_mm"], atol=2e-7)
    out = AUDIT / f"{case}_nickel_evolution.json"
    passed = errs["current_point_length"] < 1e-5
    result = {
        "case": case,
        "verdict_sha256": digest(verdict),
        "native_rst_sha256": sha["tear.rst"],
        "input_sha256": sha["model.inp"],
        "POST1_sha256": sha[name],
        "nickel_mesh_sha256": mesh_sha,
        "native_limit_sha256": scope_sha,
        "DPF_displacements_sha256": cached,
        "native_converged_sets": int(physical.sum()),
        "excluded_diagnostic_sets": int((~physical).sum()),
        "supported_sets": len(history),
        "in_plane_integration_points": nip,
        "saved_thickness_sections": list(SECTIONS),
        "saved_corner_slots_per_section": 4,
        "shell_elements": len(elements),
        "full_degradation_plastic_displacement_mm": uf,
        "damage_cap": cap,
        "maximum_absolute_damage_discrepancy": errs,
        "reconstruction_checked_at_positive_damage": bool(active) and passed,
        "first_positive_native_damage": first,
        "half_damage_native_bracket": half,
        "last_supported": summary[-1] if summary else None,
        "native_damage_states": [] if job["coupon"] else [s for s in summary if s["damaged_sites"]],
        "scope": "Post-initiation displacement reconstructed from saved accumulated plastic strain minus the strain at onset, "
        "times the length at the deformed in-plane quadrature site. The local length uses the bilinear shell "
        "Jacobian projected on its midsurface normal. The site and section-average damage are dimensionless. "
        "Cell travel and crack opening are separate quantities. Only the retained bottom, top and middle "
        "sections are observed. Cased fixtures stop at their own material and contact screen.",
    }
    write_json(out, result)
    print(case, len(history), len(active), errs, "last", result["last_supported"], flush=True)
    if active and not passed:
        raise ValueError(
            f"{case} damage evolution needs review: maximum absolute discrepancy {errs['current_point_length']}"
        )
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cases", nargs="+")
    for c in p.parse_args().cases:
        audit(c)

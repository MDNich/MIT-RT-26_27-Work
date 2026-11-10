"""Recover the maximum printed-case tension at the vibration level where a monitored contact first changes."""

import argparse

import numpy as np
from ansys.mapdl.reader.rst import ELEMENT_INDEX_TABLE_KEYS
from audit_local import ROOT, read
from case_stress import case_elements, corners, source
from film_identity import digest, write_json
from installation_material import PLA
from local_equilibrium import positions
from seeded_motion import FS
from snug_board_pull import AUDIT, CAMPAIGN
from snug_contact_vibration import BRANCHES
from snug_pla_vibration import full_coordinates
from startup_pla import components, values


def static_values(base, metric):
    return base[:, 3] if metric == "layer_tension_MPa" else base[:, 0] + np.hypot(base[:, 1], base[:, 2])


def run(branch):
    limit_path = AUDIT / f"{branch}_vibration_level.json"
    levels = read(limit_path)
    modal, folder, modes = source(branch + "_basis", CAMPAIGN)
    preload, _, static = source(branch + "_static", CAMPAIGN)
    assert modal["rst_sha256"] == levels["modal_rst_sha256"]
    elements = case_elements(static, branch)
    np.testing.assert_array_equal(elements, case_elements(modes, branch))
    nodes, locked = corners(static, static.nsets - 1, "ENS", elements, 6)
    full_base = components(locked)
    material_path = ROOT / "validation/installation_material" / f"{branch}_static.json"
    installation = read(material_path)
    assert installation["rst_sha256"] == preload["rst_sha256"]
    metrics = ("layer_tension_MPa", "in_plane_tension_MPa")
    axes = {}
    candidates = {}
    rows = []
    data = {}
    for ax, s in levels["axes"].items():
        method = "native" if s["native_MCF_sha256"] else "exact"
        path = AUDIT / f"{branch}_{ax}_PLA_{method}.json"
        stress = read(path)
        assert (
            stress["native_basis_sha256"] == modal["rst_sha256"]
            and stress["native_static_sha256"] == preload["rst_sha256"]
        )
        assert stress["input_sha256"] == s["input_sha256"]
        alpha = s["methods"][s["selected"]]["first"]["scale"]
        assert 0 < alpha < 1
        data[ax] = {"method": method, "alpha": alpha, "stress": stress}
        axes[ax] = {"scale": alpha, "full_stress_audit_sha256": digest(path), "metrics": {}}
        for metric in metrics:
            s0 = static_values(full_base, metric)
            np.testing.assert_allclose(s0.max(), installation["history"][-1]["all_" + metric], rtol=1e-6)
            peak = stress["scopes"]["all"][metric]
            assert peak["corners_in_scope"] == len(nodes) and peak["coupon_reference_MPa"] == PLA[metric]
            # Both normal stress and maximum in-plane principal stress are convex in the stress tensor.
            # At each corner the full-waveform global peak bounds its alpha=1 value at every time.
            upper = (1 - alpha) * s0 + alpha * peak["maximum_MPa"]
            keep = np.flatnonzero(upper >= s0.max() - 1e-8)
            anchor = np.flatnonzero((np.repeat(elements, 4) == peak["element"]) & (nodes == peak["node"])).item()
            candidates[(ax, metric)] = (keep, anchor)
            rows.extend(keep)
            rows.append(anchor)
            axes[ax]["metrics"][metric] = {
                "locked_maximum_MPa": float(s0.max()),
                "full_record_upper_bound_MPa": float(upper.max()),
                "candidates": len(keep),
                "total_corners": len(s0),
            }
    retained = np.unique(rows)
    rows_by_element = np.unique(retained // 4)
    selected = elements[rows_by_element]
    order = np.argsort(modes._eeqv)
    ix = order[positions(modes._eeqv[order], selected)]
    np.testing.assert_array_equal(modes.mesh.enum[ix], selected)
    native_nodes = np.array([modes.mesh.elem[i][10:14] for i in ix])
    np.testing.assert_array_equal(native_nodes, nodes.reshape(-1, 4)[rows_by_element])
    sub = np.searchsorted(rows_by_element, retained // 4) * 4 + retained % 4
    fields = np.empty((len(retained), 4, modes.nsets))
    for k in range(modes.nsets):
        offsets, _, offset = modes._element_solution_header(k)
        records = modes._cfile.read_element_data(offsets[ix], ELEMENT_INDEX_TABLE_KEYS.index("ENS"), offset)
        stress = np.stack(records).reshape(len(selected) * 4, 6)[sub].astype(float)
        fields[:, :, k] = components(stress)
    for ax, values_at_axis in data.items():
        alpha = values_at_axis["alpha"]
        method = values_at_axis["method"]
        q, qsha, isha = full_coordinates(branch, CAMPAIGN, method, ax, modal, folder, modes.time_values)
        evidence = values_at_axis["stress"]
        assert (
            qsha == evidence["coordinate_source_sha256"]
            and isha == evidence["input_sha256"]
            and len(q) == evidence["history_samples"]
        )
        for metric in metrics:
            keep, anchor = candidates[(ax, metric)]
            peak = evidence["scopes"]["all"][metric]
            qq = q[peak["sample"] : peak["sample"] + 1]
            leading = values(qq, full_base[[anchor]], fields[np.searchsorted(retained, [anchor])], metric).item()
            np.testing.assert_allclose(leading, peak["maximum_MPa"], rtol=1e-7, atol=1e-6)
            scoped = fields[positions(retained, keep)]
            base = full_base[keep]
            best = (-np.inf, 0, 0)
            for start in range(0, len(q), 8192):
                block = values(q[start : start + 8192] * alpha, base, scoped, metric)
                t, i = np.unravel_index(block.argmax(), block.shape)
                if block[t, i] > best[0]:
                    best = (float(block[t, i]), start + int(t), int(keep[i]))
            val, sample, i = best
            item = axes[ax]["metrics"][metric]
            assert item["locked_maximum_MPa"] - 1e-8 <= val <= item["full_record_upper_bound_MPa"] + 1e-8
            item.update(
                maximum_MPa=val,
                percent_of_coupon_mean=100 * val / PLA[metric],
                coupon_reference_MPa=PLA[metric],
                sample=sample,
                element=int(elements[i // 4]),
                node=int(nodes[i]),
                time_s=sample / FS,
            )
        print(
            branch,
            ax,
            [
                (m, r["candidates"], r["maximum_MPa"], r["percent_of_coupon_mean"])
                for m, r in axes[ax]["metrics"].items()
            ],
            flush=True,
        )
    write_json(
        AUDIT / f"{branch}_vibration_level_stress.json",
        {
            "branch": branch,
            "level_audit_sha256": digest(limit_path),
            "preload_material_audit_sha256": digest(material_path),
            "axes": axes,
            "scope": "Maximum tensile stress over all unaveraged PLA corners and all nine seconds at the "
            "sampled first monitored change in the installed tangent. The static load is unchanged. "
            "Convexity bounds screen out corners below the observed at-rest maximum. Remaining "
            "corners are searched at every original waveform station. Coupon means are printed "
            "material references, with no design or fatigue factor included.",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branches", nargs="+", choices=BRANCHES)
    for b in parser.parse_args().branches:
        run(b)

"""Compare the three cells at matched times and loads across bare and snug board startup histories."""

import numpy as np
from case_stress import source
from early_cell_clearance import bezier, subdivision_weights
from film_identity import digest, verified, write_json
from seeded_motion import FS
from snug_board_pull import AUDIT, BODIES, CAMPAIGN, ROOT, read
from snug_contact_startup import exact_check
from snug_contact_vibration import BRANCHES, CACHE, coordinates
from snug_pocket_release import certify_pair, witness_elements
from snug_shell_drive_sampling import native_startup
from snug_surface_distance import surface_distance


def matched():
    samples = np.arange(2049)
    time = samples / FS
    bare, folder, raw = source("bare_basis", CAMPAIGN)
    ref = read(ROOT / "validation/cell_force/bare.json")
    assert ref["basis_rst_sha256"] == bare["rst_sha256"]
    lookup = folder.parents[2] / "post" / CAMPAIGN / "bare_basis" / "cell_mass_mean.npz"
    verified(lookup, ref["mean_shapes_sha256"])
    with np.load(lookup) as d:
        means = d["mean"][[np.flatnonzero(d["materials"] == m).item() for m in BODIES]]
        np.testing.assert_array_equal(raw.time_values, d["frequencies_Hz"])
    storage = {}
    studies = {}
    for branch in BRANCHES:
        bp = AUDIT / f"{branch}_contact_vibration_basis.json"
        br = read(bp)
        vp = AUDIT / f"{branch}_contact_vibration.json"
        v = read(vp)
        assert v["basis_proof_sha256"] == digest(bp)
        folder = CACHE / (branch + "_basis") / f"coupled_contact_b{br['residual_blocks']}"
        verified(folder / "basis.npz", br["basis_sha256"])
        cp = AUDIT / f"{branch}_contact_vibration_centres.json"
        cr = read(cp)
        assert cr["basis_sha256"] == br["basis_sha256"]
        verified(folder / "cell_centres.npz", cr["centre_shapes_sha256"])
        with np.load(folder / "basis.npz") as bf:
            dat = {k: bf[k] for k in bf.files}
        with np.load(folder / "cell_centres.npz") as cf:
            centres = cf["mean"]
        studies[branch] = {
            "basis_sha256": br["basis_sha256"],
            "centre_audit_sha256": digest(cp),
            "startup_sha256": digest(vp),
        }
        storage[branch] = (folder, br, v, dat, centres)
    results = {}
    curves = {}
    for h, axis in enumerate("XYZ"):
        bare_motion = read(ROOT / "validation/independent_motion" / f"bare_motion_{axis}.json")
        bare_q, native_id = native_startup(bare_motion, CAMPAIGN, raw.time_values, samples)
        bare_displacement = 1e6 * np.einsum("tb,ijb->tij", bare_q, means)
        traces = {}
        for branch, (folder, br, v, dat, centres) in storage.items():
            f = folder / (axis + "_history.npz")
            verified(f, v["axes"][axis]["history_sha256"])
            with np.load(f) as d:
                traces[branch] = {
                    k: d[k]
                    for k in ("load", "signed_compression_m", "time_ms", "point_and_spacer_force_N")
                }
            assert bare_motion["input_sha256"] == v["axes"][axis]["input_sha256"]
            np.testing.assert_allclose(traces[branch]["time_ms"], 1000 * time)
        common = np.min(
            np.stack([-x["signed_compression_m"][:, :-4].max(1) for x in traces.values()]), axis=0
        )
        station = int(np.argmax(common))
        assert common[station] > 0

        def travel(u, station=station):
            z = u[:, 1, 2]
            pos = int(np.argmax(abs(z)))
            return {
                "middle_Z_um_at_common": float(z[station]),
                "middle_peak_abs_Z_um": float(abs(z[pos])),
                "peak_time_ms": 1e3 * time[pos],
                "left_middle_X_approach_um_at_common": float(u[station, 0, 0] - u[station, 1, 0]),
            }

        group = {"bare": travel(bare_displacement)}
        curves[axis + "_bare"] = bare_displacement[:, 1, 2]
        for branch, (folder, br, v, data, centres) in storage.items():
            om, B, drive, T = coordinates(data, br["residual_blocks"])
            n = br["native_modes"]
            q, _ = exact_check(om, B, data["k"], data["g"], drive[:, h], traces[branch]["load"], 4)
            q = q[::4]
            signed = data["g"] + q @ B
            recorded = traces[branch]["signed_compression_m"]
            err = np.linalg.norm(signed - recorded) / np.linalg.norm(recorded)
            assert err < 0.005 and (signed[station, :-4] < 0).all(), err
            native_basis = np.column_stack((q[:, :n], q[:, n:] @ T.T))
            u = 1e6 * np.einsum("tb,ijb->tij", native_basis, centres)
            # Compare at the native installed-mode cutoff on the same previously registered seeds.
            motion = read(ROOT / "validation/independent_motion" / f"{branch}_motion_{axis}.json")
            if (ROOT / "validation/motion" / (motion["case"] + ".json")).is_file():
                frozen, source_id = native_startup(motion, CAMPAIGN, data["frequency"], samples)
            else:
                from film_cell_timestep import refined_coordinates
                from seeded_motion import participation

                log = (
                    ROOT / ".runtime/archive" / CAMPAIGN / (branch + "_basis") / "solve.out"
                ).read_text(errors="replace")
                frozen, _ = refined_coordinates(
                    "linear_input_exact",
                    traces[branch]["load"],
                    samples,
                    data["frequency"],
                    participation(log, axis),
                )
                source_id = {"method": "independent exact integration of retained native modes"}
            frozen_u = 1e6 * np.einsum("tb,ijb->tij", frozen, centres[:, :, :n])
            xyz = 1000 * (
                data["positions"] + np.einsum("ijk,k->ij", data["skin"], native_basis[station])
            )
            case = bezier(xyz[data["case"]])
            geometry = {}
            for name in ("left", "middle", "right"):
                cell = bezier(xyz[data[name]])
                check = certify_pair(case, cell, subdivision_weights())
                assert check["state"] in ("separated", "intersecting")
                if name == "middle" and check["state"] == "separated":
                    check["clearance"] = surface_distance(case, cell)
                if name == "middle" and check["state"] == "intersecting":
                    _, _, mesh = source(branch + "_basis", CAMPAIGN)
                    witness = check["witness"]
                    numbers = witness_elements(
                        mesh,
                        data["nodes"][data["case"][witness["PLA_face"]]],
                        data["nodes"][data["middle"][witness["cell_face"]]],
                    )
                    loaded = read(AUDIT / f"{branch}_pocket_face_unloading.json")["elements"]
                    check["witness_elements"] = numbers
                    check["witness_case_face_loaded_at_lock"] = numbers["case_contact_element"] in loaded
                geometry[name] = check
            group[branch] = dict(
                **travel(u),
                original_mode_result=travel(frozen_u),
                original_coordinates=source_id,
                common_time_global_surfaces=geometry,
                exact_vs_refined_gap_relative_error=float(err),
            )
            curves[axis + "_" + branch] = u[:, 1, 2]
            curves[axis + "_" + branch + "_force"] = traces[branch]["point_and_spacer_force_N"][
                :, :-4
            ].sum(1)
        results[axis] = {
            "station": station,
            "time_ms": 1000 * time[station],
            "bare_coordinate_source": native_id,
            "matched_input_sha256": bare_motion["input_sha256"],
            "models": group,
        }
        print(
            axis,
            results[axis]["time_ms"],
            {
                k: (
                    m["middle_Z_um_at_common"],
                    m.get("common_time_global_surfaces", {}).get("middle", {}).get("state"),
                )
                for k, m in group.items()
            },
            flush=True,
        )
    out = CACHE / "matched_contact_startup.npz"
    np.savez(out, time_ms=time * 1000, **curves)
    write_json(
        AUDIT / "matched_contact_startup.json",
        {
            "axes": results,
            "history_sha256": digest(out),
            "source_studies": studies,
            "bare_modal_rst_sha256": bare["rst_sha256"],
            "bare_mass_mean_sha256": ref["mean_shapes_sha256"],
            "scope": "One common sample per input maximizing the smallest opening among all originally loaded pocket points in all three cased reductions. The surface classification and clearance are evaluated at exactly that sample. Bare motion uses native modal coordinates. The cased comparison uses unilateral springs at original points and spacers only.",
        },
    )


if __name__ == "__main__":
    matched()

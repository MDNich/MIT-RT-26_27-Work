"""Find where the installed middle-pocket tangent exhausts its net compressive reaction."""

import argparse

import numpy as np
from basis_comparison import field_files
from case_stress import source
from film_cell_timestep import refined_coordinates
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from seeded_motion import FS, integrate, participation
from snug_board_pull import AUDIT, CAMPAIGN, ROOT, positions, read
from snug_pocket_preload import bracket, normal_controls
from snug_shell_drive_sampling import native_startup


def run(branch):
    equilibrium = AUDIT / f"{branch}_locked_pocket_equilibrium.json"
    load_path = AUDIT / f"{branch}_initial_cell_load_paths.json"
    balance, tangent = read(equilibrium), read(load_path)
    assert balance["branch"] == tangent["branch"] == branch
    proof, folder, modal = source(branch + "_basis", CAMPAIGN)
    force_checks = tangent["modal_check"]
    assert proof["rst_sha256"] == force_checks["rst_sha256"]
    assert sorted(balance["active_elements"]) == sorted(tangent["installed_contact_elements"])
    full = AUDIT / f"{branch}_full_board_tangent.json"
    verified(full, tangent["full_tangent_sha256"])
    assert (
        read(full)["static_rst_sha256"] == read(AUDIT / f"{branch}_static_contacts.json")["rst_sha256"]
    )
    if balance["static_case"] != branch + "_static":
        repeat = read(AUDIT / (branch.removeprefix("snug125_") + "_pocket_preload.json"))
        assert repeat["reference_static_rst_sha256"] == read(full)["static_rst_sha256"]
        assert repeat["native_force_rst_sha256"] == balance["rst_sha256"]
        assert max(repeat["all_station_displacement_repeat_max_m"]) < 1e-9

    # The modal ENF from the cell side was independently reproduced by K-M omega^2
    # on the PLA solid and by the negative contact-element force on its PLA nodes.
    assert force_checks["relative_force_errors"]["PLA pocket"] < 1.0e-6
    assert force_checks["relative_force_errors"]["contact elements"] < 1.0e-6
    cache = ROOT / ".runtime/post" / CAMPAIGN / proof["case"] / "attachment_modes.npz"
    verified(cache, force_checks["native_force_shapes_sha256"])
    with np.load(cache) as data:
        assert np.array_equal(modal.time_values, data["frequency_Hz"])
        forces = data["middle_cell_pocket_force"]
    candidates = balance["force_into_shell_XYZ_N"]
    selected = "native_contact" if "native_contact" in candidates else "PLA_pocket"
    preload = np.array(candidates[selected])
    # A positive increment along this axis consumes compression in the original patch.
    axis = -preload / np.linalg.norm(preload)
    levels = {source: float(-np.dot(vec, axis)) for source, vec in candidates.items()}
    assert min(levels.values()) > 0
    loading = np.array(tangent["element_group_XYZ_N_per_N"]["PLA pocket"])
    slope = axis @ loading
    assert (slope[[0, 2]] > 0).all() and slope[1] < 0
    sensitivity = {key: (value / slope).tolist() for key, value in levels.items()}

    face_ids = np.array(balance["active_six_node_faces"])
    xyz = np.array(balance["lock_patch_xyz_m"])
    assert np.max(abs(modal.mesh.nodes[positions(modal.mesh.nnum, face_ids)] - xyz)) < 1.0e-10
    nodes = np.unique(face_ids)
    shape = displacement_basis(
        modal, nodes, field_files(proof["case"], CAMPAIGN, proof["rst_sha256"], modal.nsets)
    )
    face_rows = positions(nodes, face_ids)

    def cosine(coordinates):
        moved = xyz + np.tensordot(coordinates, shape, axes=1)[face_rows]
        normals = np.stack([normal_controls(face) for face in moved])
        lower = (normals @ axis).min(1) / np.linalg.norm(normals, axis=2).max(1)
        assert lower.min() > 0.95
        return float(lower.min())

    initial_cosine = cosine(np.zeros(modal.nsets))
    projections = axis @ forces
    samples = np.arange(round(0.08 * FS) + 1)
    axes = {}
    for direction in "XYZ":
        datafile = ROOT / "validation/independent_motion" / f"{branch}_motion_{direction}.json"
        spec = read(datafile)
        assert spec["basis_rst_sha256"] == proof["rst_sha256"]
        listing = folder / "solve.out"
        verified(listing, spec["modal_listing_sha256"])
        load = ROOT / ".runtime/motion_loads" / f"{direction}.txt"
        verified(load, spec["input_sha256"])
        gamma = participation(listing.read_text(errors="replace"), direction)
        _, q, _ = integrate(modal.time_values, gamma, direction, samples)
        accel = np.loadtxt(load, skiprows=1, max_rows=len(samples))
        assert np.allclose(accel[:, 0], samples / FS, atol=5.1e-13, rtol=0)
        exact, exact_control = refined_coordinates(
            "linear_input_exact", accel[:, 1], samples, modal.time_values, gamma
        )
        coords = {"Newmark": q, "exact_linear_input": exact}
        native = {}
        if (ROOT / "validation/motion" / f"{branch}_motion_{direction}.json").is_file():
            coords["native"], native = native_startup(spec, CAMPAIGN, modal.time_values, samples)
        records = {}
        for method, history in coords.items():
            value = history @ projections
            crossing = bracket(value, levels[selected], 1)
            k = crossing["sample"]
            tested = {src: bracket(value, level, 1)["sample"] for src, level in levels.items()}
            cutoffs = {}
            for cutoff in (2000, 3000, 3500, 4000):
                keep = modal.time_values <= cutoff
                cutoffs[cutoff] = bracket(history[:, keep] @ projections[keep], levels[selected], 1)[
                    "sample"
                ]
            records[method] = {
                "first_crossing": crossing,
                "normal_cosine_at_first_crossing": cosine(history[k]),
                "projected_total_force_into_case_N": (levels[selected] - value[k - 1 : k + 1]).tolist(),
                "crossing_sample_by_preload_source": tested,
                "crossing_sample_by_cutoff_Hz": cutoffs,
            }
        axes[direction] = {
            "input_sha256": spec["input_sha256"],
            "listing_sha256": spec["modal_listing_sha256"],
            "independent_motion_sha256": digest(datafile),
            "native_coordinate_source": native,
            "exact_integrator_control": exact_control,
            "integrations": records,
        }
    out = {
        "branch": branch,
        "locked_equilibrium_sha256": digest(equilibrium),
        "initial_load_paths_sha256": digest(load_path),
        "modal_force_shapes_sha256": force_checks["native_force_shapes_sha256"],
        "modal_rst_sha256": proof["rst_sha256"],
        "selected_preload_source": selected,
        "opening_direction": axis.tolist(),
        "projected_compression_N": levels,
        "minimum_installed_normal_cosine": initial_cosine,
        "load_order": tangent["load_order"],
        "opening_force_increment_N_per_unit_positive_X_load": slope.tolist(),
        "signed_applied_X_N_at_zero_compression_by_source": sensitivity,
        "axes": axes,
        "scope": "The middle pocket is frictionless and unilateral. A negative net compressive projection is incompatible "
        "with the installed set of contact faces. Each applied-load intercept extrapolates the initial stiffness; "
        "redistribution or engagement elsewhere can precede it. Each time bracket locates this test on the fixed-contact "
        "vibration trajectory. Actual opening, reseating and impact require changing contact.",
    }
    write_json(AUDIT / f"{branch}_pocket_unloading.json", out)
    print(
        branch,
        levels[selected],
        "applied X for zero compression",
        sensitivity[selected],
        "times ms",
        {
            d: 1000
            * r["integrations"].get("native", r["integrations"]["exact_linear_input"])["first_crossing"][
                "sample"
            ]
            / FS
            for d, r in axes.items()
        },
        flush=True,
    )


def compare_native_repeat(branch, case, displacement_errors):
    """Keep the original independent prediction and compare the output-only repeat at lock."""
    root = AUDIT / f"{branch}_pocket_unloading.json"
    if not root.is_file():
        return
    original = read(root)
    assert original["branch"] == branch and case == branch + "_out2_static"
    prior = AUDIT / f"{branch}_locked_pocket_equilibrium.json"
    verified(prior, original["locked_equilibrium_sha256"])
    native = AUDIT / f"{case}_contacts.json"
    state = read(native)
    parent = read(AUDIT / f"{branch}_static_contacts.json")
    assert state["case"] == case and state["contact_history"] == parent["contact_history"]
    assert len(displacement_errors) == len(state["contact_history"]) and max(displacement_errors) < 1e-9
    force = state["resultant_force_check"][-1]
    assert (
        force["native_set"] == state["contact_history"][-1]["native_set"]
        and state["contact_history"][-1]["load_time"] == 2.0
    )
    assert force["maximum_POST1_difference_N"] < 1e-5
    axis = np.array(original["opening_direction"])
    incoming = -np.array(force["force_xyz_N"])
    compression = float(-incoming @ axis)
    assert compression > 0
    slope = np.asarray(original["opening_force_increment_N_per_unit_positive_X_load"])
    measured = read(prior)
    diff = {
        name: float(np.linalg.norm(np.array(vec) - incoming))
        for name, vec in measured["force_into_shell_XYZ_N"].items()
    }
    rev = {
        "case": case,
        "prediction_sha256": digest(root),
        "locked_solid_equilibrium_sha256": digest(prior),
        "native_contact_audit_sha256": digest(native),
        "repeat_rst_sha256": state["rst_sha256"],
        "maximum_displacement_difference_m": max(displacement_errors),
        "native_force_into_PLA_XYZ_N": incoming.tolist(),
        "difference_from_native_by_source_N": diff,
        "native_compression_on_original_axis_N": compression,
        "native_preload_based_applied_X_N_at_zero_compression": (compression / slope).tolist(),
        "load_order": original["load_order"],
        "scope": "Same nominal mesh and physical deck. Only the contact output request changed. "
        "The zero-compression intercept still uses the original fixed-contact tangent.",
    }
    write_json(AUDIT / f"{branch}_pocket_force_repeat_check.json", rev)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branch")
    run(parser.parse_args().branch)

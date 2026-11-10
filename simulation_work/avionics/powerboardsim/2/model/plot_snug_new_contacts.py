"""Show where newly reached points would press on the middle battery at the matched base-Y pose."""

import numpy as np
from film_identity import digest, verified, write_json
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read
from snug_contact_vibration import CACHE


def cad_check(branch):
    from snug_pocket_depth import check_cad_witnesses
    from snug_pocket_faces import SHAPE
    from snug_pocket_sampling import cylinder_correction, groups, positions, shape

    d = read(AUDIT / f"{branch}_pocket_sampling.json")
    bpath = CACHE / (branch + "_basis") / "coupled_contact_b5" / "basis.npz"
    with np.load(bpath) as f:
        data = {k: f[k] for k in ("case", "nodes", "middle")}
    (cap, cell), _ = groups(branch, data)
    proof = read(AUDIT / "aluminium_curved_pocket_depth.json")
    tags = [s["installed_gmsh_face"] for s in proof["registered_CAD"]["cylinders"]]
    rows = [s for s in d["axes"]["Y"]["matched"] if s["surface"] == "STEP" and s["gap_um"] < 0]
    pts = []
    faces = []
    for r in rows:
        v = SHAPE[:, r["gp"] - 1] @ cap[2][positions(cap[0], [r["element"]])[0]]
        vals, _, _ = shape(np.array([r["uv"]]))
        w = vals[0] @ cell[2][positions(cell[0], [r["target"]])[0]]
        for x, ts, tag in zip([v, w], [cap, cell], tags):
            x = x.copy()
            delta, _, _ = cylinder_correction(x[None], ts[3], ts[4])
            x += delta[0]
            pts.append(x)
            faces.append(tag)
    err = check_cad_witnesses(pts, faces)
    return {"checked_surface_points": len(pts), "maximum_trimmed_surface_error_mm": err}


def draw():
    fig, axes = plt.subplots(1, 2, figsize=(8.05, 2.45), layout="constrained", sharey=True)
    matched = AUDIT / "matched_contact_startup.json"
    station = read(matched)["axes"]["Y"]["station"]
    records = []
    for b, label, color, marker in (
        ("nylon", "Nylon, 2 mm", "#08357E", "o"),
        ("nylon_mesh15", "Nylon, 1.5 mm", "#3C78D8", "D"),
        ("aluminium", "Aluminium, 2 mm", "#38761D", "s"),
    ):
        branch = "snug125_" + b
        file = AUDIT / f"{branch}_prescribed_contact_check.json"
        rings = AUDIT / f"{branch}_pocket_sampling.json"
        verify, trace = read(file), read(rings)
        assert verify["matched_pose_sha256"] == trace["matched_station_sha256"] == digest(matched)
        r = verify["matched_base_Y"]
        assert r["sample"] == station
        opening = trace["axes"]["Y"]
        marked = [p for p in opening["matched"] if p["surface"] == "mesh" and p["gap_um"] < 0]
        index = {(p["element"], p["gp"]): p for p in marked}
        assert (
            len(index)
            == len(r["points"])
            == opening["events"]["mesh"]["initially_unloaded"]["matched_negative_points"]
        )
        assert not any(p["active_at_lock"] for p in marked)
        for point in r["points"]:
            same = index[point["element"], point["point"]]
            assert abs(point["radial_penetration_um"] + same["gap_um"]) < 1e-7
        for axis, row in trace["axes"].items():
            loc = CACHE / (branch + "_basis") / "coupled_contact_b5" / (axis + "_pocket_sampling.npz")
            verified(loc, row["history_sha256"])
            with np.load(loc) as raw:
                samples = raw["samples"]
                gaps = raw["minimum_gap_mm"][:, 0, 1]
                first = row["events"]["mesh"]["initially_unloaded"]["first_negative_sample"]
                assert (
                    np.array_equal(samples[: first + 1], np.arange(first + 1))
                    and np.all(gaps[:first] >= -1e-9)
                    and gaps[first] < -1e-9
                )
        xs = [p["from_low_Y_barrel_end_mm"] for p in r["points"]]
        ys = [p["pressure_MPa"] for p in r["points"]]
        for ax in axes:
            ax.scatter(
                xs,
                ys,
                s=37,
                marker=marker,
                edgecolor=color,
                facecolor="white" if marker == "D" else color,
                label=label,
            )
        records.append(
            {
                "branch": branch,
                "trimmed_STEP_check": cad_check(branch),
                "force_check_sha256": digest(file),
                "sampling_sha256": digest(rings),
                "mesh_points": len(xs),
                "force_on_case_XYZ_N": r["force_on_case_XYZ_N"],
                "resultant_N": r["total_N"],
                "pressure_range_MPa": [min(ys), max(ys)],
                "axial_range_mm": [min(xs), max(xs)],
                "STEP_points": opening["events"]["STEP"]["initially_unloaded"][
                    "matched_negative_points"
                ],
            }
        )
    axes[0].set(
        xlim=(0, 16), xticks=[0, 4, 8, 12, 16], title="Low-Y end", ylabel="Estimated pressure [MPa]"
    )
    axes[1].set(xlim=(65, 70), xticks=[65, 66, 67, 68, 69, 70], title="High-Y end")
    for ax in axes:
        ax.set(ylim=(0, 1.60), xlabel="Distance from low-Y end [mm]")
        ax.grid(alpha=0.14)
        ax.spines[["right", "top"]].set_visible(False)
    fig.legend(
        *axes[0].get_legend_handles_labels(),
        loc="outside lower center",
        ncol=3,
        frameon=False,
        fontsize=9,
    )
    fig.savefig(
        ROOT / "docs/figures/snug-new-contact-sites.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)
    write_json(
        AUDIT / "new_contact_sites_comparison.json",
        {"matched_sha256": digest(matched), "axis": "Y", "sample": station, "models": records},
    )


if __name__ == "__main__":
    draw()

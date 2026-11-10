"""Show how the mounted board responds as loaded portions of the middle pocket open."""

import numpy as np
from film_identity import digest, write_json
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read


def summary(branch, bare):
    file = AUDIT / f"{branch}_spacer_pocket_pull.json"
    data = read(file)
    force_file = AUDIT / f"{branch}_pocket_face_unloading.json"
    assert data["face_preload_sha256"] == digest(force_file)
    force = read(force_file)
    models = read(AUDIT / f"{branch}_initial_cell_load_paths.json")["element_group_XYZ_N_per_N"]
    assert data["seat_preload_sha256"] == digest(AUDIT / f"{branch}_spacer_bearing.json")
    checks = {}
    for load, axis, sign in (("left_plus_X", 0, 1), ("middle_minus_X", 1, -1)):
        whole = data["paths"][load]
        rows = whole["states"]
        init, end = rows[0], rows[-1]
        first = rows[1]
        assert init["applied_magnitude_N"] == 0 and end["applied_magnitude_N"] == 8.54205
        labels = data["contact_labels"][:-4]
        normals = {
            f"{p['element']}.{p['point']}": np.array(p["normal"]) for p in force["integration_points"]
        }
        first_derivative = (
            np.array(first["projected_compression_N"]) - init["projected_compression_N"]
        ) / first["applied_magnitude_N"]
        errors = []
        for elem in force["elements"]:
            combined = sum(
                normals[name] * first_derivative[i]
                for i, name in enumerate(labels)
                if name.startswith(str(elem) + ".")
            )
            ref = np.array(models["contact " + str(elem)])[:, axis] * sign
            errors.append(float(np.linalg.norm(combined - ref)))
        assert max(errors) < 5e-7, (branch, load, max(errors))
        switch = []
        for previous, current in zip(whole["intervals"], whole["intervals"][1:]):
            before = set(previous["bearing"])
            after = set(current["bearing"])
            switch.append(
                {
                    "force_N": current["start_N"],
                    "new_bearing": sorted(after - before),
                    "released": sorted(before - after),
                }
            )
        cased = abs(end["cell_X_um"][axis])
        naked = bare[axis, axis] * end["applied_magnitude_N"]
        checks[load] = {
            "endpoint_um": cased,
            "bare_endpoint_um": naked,
            "travel_reduction_percent": 100 * (1 - cased / naked),
            "first_slope_max_face_force_error_N_per_N": max(errors),
            "transitions": switch,
            "original_pocket_sum_of_compression_N": sum(end["projected_compression_N"][:-4]),
        }
    return data, {"branch": branch, "path_sha256": digest(file), "loads": checks}


def draw():
    bare_file = AUDIT / "bare_full_board_tangent.json"
    bare = np.array(read(bare_file)["cell_X_um_per_N"])
    fig, (left, right) = plt.subplots(1, 2, figsize=(8.0, 2.65), layout="constrained")
    rows = []
    for b, label, color, style in (
        ("nylon", "Nylon, 2 mm", "#08357E", "-"),
        ("nylon_mesh15", "Nylon, 1.5 mm", "#3C78D8", "--"),
        ("aluminium", "Aluminium, 2 mm", "#38761D", "-"),
    ):
        data, check = summary("snug125_" + b, bare)
        rows.append(check)
        path = data["paths"]["middle_minus_X"]["states"]
        x = np.array([r["applied_magnitude_N"] for r in path])
        c = np.array([sum(r["projected_compression_N"][:-4]) for r in path])
        centre = np.array([abs(r["cell_X_um"][1]) for r in path])
        left.plot(x, c, color=color, linestyle=style, label=label, lw=1.5)
        left.scatter(x[1:-1], c[1:-1], s=8, color=color, zorder=2)
        # Travel is piecewise linear between equilibrium changes.
        line = np.linspace(1e-6, x[-1], 350)
        right.plot(
            line,
            100 * (1 - np.interp(line, x, centre) / (bare[1, 1] * line)),
            color=color,
            linestyle=style,
            lw=1.5,
        )
    left.set(
        ylabel="Sum of original point forces [N]",
        xlabel="Side load on middle cell [N]",
        title="Compression remaining in pocket",
    )
    right.set(
        ylabel=r"Reduction in travel [\% of bare]",
        xlabel="Side load on middle cell [N]",
        title="Middle-cell travel relative to bare",
    )
    for ax in (left, right):
        ax.set(xlim=(0, 8.65), xticks=[0, 2, 4, 6, 8])
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.15)
    fig.legend(
        *left.get_legend_handles_labels(), loc="outside lower center", ncol=3, frameon=False, fontsize=9
    )
    fig.savefig(
        ROOT / "docs/figures/snug-switching-pocket-pull.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)
    write_json(
        AUDIT / "switching_pocket_pull_comparison.json",
        {"bare_sha256": digest(bare_file), "models": rows},
    )


if __name__ == "__main__":
    draw()

"""Plot the compressive force left in the middle pocket and its loss on each vibration record."""

from film_identity import verified
from report_plot import plt
from seeded_motion import FS
from snug_board_pull import AUDIT, ROOT, read


def draw():
    fig, (static, dynamic) = plt.subplots(1, 2, figsize=(8.25, 2.85), layout="constrained")
    cases = (
        ("snug125_nylon", "Nylon, 2 mm", "#08357E", "o", "-"),
        ("snug125_nylon_mesh15", "Nylon, 1.5 mm", "#3C78D8", "s", "--"),
        ("snug125_aluminium", "Aluminium, 2 mm", "#38761D", "D", "-"),
    )
    intercepts = []
    for i, (branch, label, color, marker, style) in enumerate(cases):
        row = read(AUDIT / f"{branch}_pocket_unloading.json")
        verified(AUDIT / f"{branch}_locked_pocket_equilibrium.json", row["locked_equilibrium_sha256"])
        verified(AUDIT / f"{branch}_initial_cell_load_paths.json", row["initial_load_paths_sha256"])
        source = row["selected_preload_source"]
        preload = row["projected_compression_N"][source]
        magnitude = -row["signed_applied_X_N_at_zero_compression_by_source"][source][1]
        slope = row["opening_force_increment_N_per_unit_positive_X_load"][1]
        assert magnitude > 0 and abs(preload + magnitude * slope) < 1e-9
        static.plot(
            [0, magnitude],
            [preload, 0],
            ls=style,
            color=color,
            lw=1.7,
            marker=marker,
            ms=4,
            label=label,
            clip_on=False,
        )
        intercepts.append(magnitude)
        for j, axis in enumerate("XYZ"):
            checks = row["axes"][axis]["integrations"]
            preferred = checks.get("native", checks["exact_linear_input"])
            k = preferred["first_crossing"]["sample"]
            assert all(r["first_crossing"]["sample"] == k for r in checks.values())
            assert all(r["crossing_sample_by_cutoff_Hz"]["3000"] == k for r in checks.values())
            ms = 1000 * k / FS
            y = 2 - j + (1 - i) * 0.21
            dynamic.plot(ms, y, marker=marker, ms=5, color=color)
            dynamic.text(ms + 0.56, y, f"{ms:.1f}", va="center", fontsize=8, color=color)
    static.annotate(
        f"{intercepts[2]:.2f} N",
        (intercepts[2], 0),
        (0.6, 0.14),
        fontsize=9,
        arrowprops={"arrowstyle": "-", "lw": 0.6, "color": "#38761D"},
        color="#38761D",
    )
    static.annotate(
        f"{intercepts[0]:.2f}--{intercepts[1]:.2f} N",
        (intercepts[0], 0),
        (3.3, 0.25),
        fontsize=9,
        arrowprops={"arrowstyle": "-", "lw": 0.6, "color": "#08357E"},
        color="#08357E",
    )
    static.set(
        xlim=(-0.08, 5.8),
        ylim=(-0.018, 0.67),
        xlabel=r"Middle-cell load in $-X$ [N]",
        ylabel="Pocket compression [N]",
        title="Initial response to a sideways force",
    )
    dynamic.set(
        xlim=(0, 29),
        ylim=(-0.45, 2.5),
        yticks=[2, 1, 0],
        yticklabels=["Base X", "Base Y", "Base Z"],
        xlabel="Time from start of vibration [ms]",
        title="First loss of net compression",
    )
    for ax in (static, dynamic):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", alpha=0.16)
        ax.set_axisbelow(True)
    fig.legend(
        *static.get_legend_handles_labels(),
        loc="outside lower center",
        ncol=3,
        frameon=False,
        fontsize=9,
    )
    fig.savefig(
        ROOT / "docs/figures/snug-middle-pocket-unloading.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


if __name__ == "__main__":
    draw()

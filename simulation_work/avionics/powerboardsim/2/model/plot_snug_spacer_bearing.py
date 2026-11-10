"""Compare the first spacer transition with unloading of the installed middle pocket."""

from film_identity import digest, write_json
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read


def first_spacer(seats, measurement):
    return min(
        (seat[measurement]["interpolated_ms"], i + 1, seat[measurement]["transition"])
        for i, seat in enumerate(seats)
        if seat[measurement] is not None
    )


def compare(branch):
    seat_path = AUDIT / f"{branch}_spacer_bearing.json"
    pocket_path = AUDIT / f"{branch}_pocket_unloading.json"
    seat, pocket = read(seat_path), read(pocket_path)
    assert seat["modal_rst_sha256"] == pocket["modal_rst_sha256"]
    checks = {}
    for axis in "XYZ":
        a, b = seat["axes"][axis], pocket["axes"][axis]
        assert a["input_sha256"] == b["input_sha256"]
        integrations = a["integrations"]
        source = "native" if "native" in integrations else "exact_linear_input"
        time, tab, event = first_spacer(integrations[source], "current_length")
        pocket_bounds = [1000 * t for t in b["integrations"][source]["first_crossing"]["time_bracket_s"]]
        spacer_first = time < pocket_bounds[0]
        assert spacer_first or time > pocket_bounds[1]
        differences = {}
        for method, seats in (integrations | a["truncated_basis"]).items():
            for geometry in ("current_length", "projected_increment"):
                t, _, _ = first_spacer(seats, geometry)
                assert (t < pocket_bounds[0]) == spacer_first
                differences[method + "_" + geometry] = t - time
        assert max(abs(d) for d in differences.values()) < 1000 / seat["sample_frequency_Hz"]
        checks[axis] = {
            "source": source,
            "seat_time_ms": time,
            "tab_number": tab,
            "transition": event,
            "pocket_bracket_ms": pocket_bounds,
            "spacer_first": spacer_first,
            "first_time_change_ms": differences,
        }
    return {
        "branch": branch,
        "spacer_sha256": digest(seat_path),
        "pocket_sha256": digest(pocket_path),
        "axes": checks,
    }


def draw():
    records = [compare("snug125_" + name) for name in ("nylon", "aluminium", "nylon_mesh15")]
    write_json(AUDIT / "spacer_startup_comparison.json", records)
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 2.45), layout="constrained", sharey=True)
    for ax, data, title in zip(axes, records[:2], ("Nylon screws", "Aluminium screws"), strict=True):
        for y, axis in enumerate("ZYX"):
            row = data["axes"][axis]
            t, p = row["seat_time_ms"], row["pocket_bracket_ms"][1]
            ax.plot((t, p), (y, y), color="#aaaaaa", linewidth=1.3, zorder=0)
            for x, mark, color, label in (
                (t, "o", "#08357E", "First spacer opens or closes"),
                (p, "s", "#38761D", "Middle pocket loses net compression"),
            ):
                ax.scatter(
                    x,
                    y,
                    s=28,
                    marker=mark,
                    edgecolor=color,
                    facecolor=color if mark == "o" else "white",
                    label=label if y == 0 else None,
                )
                dx = -5 if x == min(t, p) else 5
                ax.annotate(
                    f"{x:.1f}",
                    (x, y),
                    xytext=(dx, 0),
                    textcoords="offset points",
                    va="center",
                    ha="right" if dx < 0 else "left",
                    fontsize=9,
                    color=color,
                )
        ax.set(
            xlim=(0, 29.5),
            ylim=(-0.4, 2.4),
            xticks=range(0, 26, 5),
            yticks=[0, 1, 2],
            yticklabels=["Base Z", "Base Y", "Base X"],
            title=title,
            xlabel="Time from start of excitation [ms]",
        )
        ax.spines[["top", "left", "right"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", alpha=0.13)
    fig.legend(
        *axes[0].get_legend_handles_labels(),
        loc="outside lower center",
        frameon=False,
        ncol=2,
        fontsize=9,
    )
    fig.savefig(
        ROOT / "docs/figures/snug-spacer-bearing.pdf", metadata={"CreationDate": None, "ModDate": None}
    )
    plt.close(fig)


if __name__ == "__main__":
    draw()

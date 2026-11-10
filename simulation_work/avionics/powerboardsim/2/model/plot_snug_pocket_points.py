"""Compare the first pocket point, first spacer switch and net-pocket force bound."""

from film_identity import verified
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read


def draw():
    seats = {r["branch"]: r for r in read(AUDIT / "spacer_startup_comparison.json")}
    fig, axes = plt.subplots(1, 3, sharex=True, sharey=True, figsize=(8.15, 2.64), layout="constrained")
    for ax, variant, title in zip(
        axes,
        ("nylon", "nylon_mesh15", "aluminium"),
        ("Nylon, 2 mm mesh", "Nylon, 1.5 mm mesh", "Aluminium, 2 mm mesh"),
        strict=True,
    ):
        branch = "snug125_" + variant
        faces = read(AUDIT / f"{branch}_pocket_face_unloading.json")
        seat = seats[branch]
        verified(AUDIT / f"{branch}_spacer_bearing.json", seat["spacer_sha256"])
        assert faces["net_audit_sha256"] == seat["pocket_sha256"]
        for y, axis in enumerate("ZYX"):
            result = faces["axes"][axis]
            hist = result["histories"][result["selected"]]
            other = seat["axes"][axis]
            assert (
                result["input_sha256"]
                == read(AUDIT / f"{branch}_pocket_unloading.json")["axes"][axis]["input_sha256"]
            )
            values = [
                hist["first_point_ms"],
                other["seat_time_ms"],
                hist["net_crossing"]["interpolated_ms"],
            ]
            ax.hlines(y, min(values), max(values), color="#a8a8a8", lw=1, zorder=1)
            for x, offset, marker, color, label in zip(
                values,
                [0.13, 0, -0.13],
                ["o", "D", "s"],
                ["#7A0101", "#08357E", "#38761D"],
                ["First pocket point unloads", "First spacer switches", "Net pocket force reaches zero"],
                strict=True,
            ):
                ax.plot(
                    x,
                    y + offset,
                    marker=marker,
                    markersize=4.8,
                    linestyle="none",
                    color=color,
                    markerfacecolor="white" if marker == "s" else color,
                    label=label if y == 0 else None,
                    zorder=3,
                )
        ax.set(
            title=title,
            xlim=(-0.5, 26.8),
            ylim=(-0.44, 2.44),
            xticks=range(0, 26, 5),
            yticks=(0, 1, 2),
            yticklabels=("Base Z", "Base Y", "Base X"),
        )
        ax.tick_params(axis="y", length=0)
        ax.spines[["left", "right", "top"]].set_visible(False)
        ax.grid(axis="x", alpha=0.15)
    axes[1].set_xlabel("Time from start of excitation [ms]")
    fig.legend(
        *axes[0].get_legend_handles_labels(),
        loc="outside lower center",
        ncol=3,
        frameon=False,
        fontsize=8.8,
    )
    fig.savefig(
        ROOT / "docs/figures/snug-pocket-point-timing.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


if __name__ == "__main__":
    draw()

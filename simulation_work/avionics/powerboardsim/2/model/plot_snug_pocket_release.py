"""Compare the first frequency and middle-cell compliance for open and seated pockets."""

from film_identity import verified
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read


def draw():
    labels = ["Bare board", "Nylon", "Nylon, finer mesh", "Aluminium"]
    controls = read(AUDIT / "bare_full_board_tangent.json")
    bare = read(ROOT / "validation/global/bare_basis.json")
    assert bare["rst_sha256"] == controls["basis_rst_sha256"]
    ref = [controls["cell_X_um_per_N"][1][1], bare["frequencies_Hz"][0]]
    pairs = []
    for branch in ("snug125_nylon", "snug125_nylon_mesh15", "snug125_aluminium"):
        record = read(AUDIT / f"{branch}_released_pocket_tangent.json")
        old = AUDIT / f"{branch}_full_board_tangent.json"
        verified(old, record["full_tangent_sha256"])
        basis = read(ROOT / "validation/global" / f"{branch}_basis.json")
        assert record["modal_rst_sha256"] == basis["rst_sha256"]
        pairs.append(
            [
                (read(old)["cell_X_um_per_N"][1][1], record["open_compliance_X_um_per_N"][1][1]),
                (basis["frequencies_Hz"][0], record["first_six_open_modes"][0]["open_Hz"]),
            ]
        )
    fig, axes = plt.subplots(1, 2, figsize=(8.05, 2.38), layout="constrained", sharey=True)
    for k, (ax, xlim, title, unit, fmt) in enumerate(
        zip(
            axes,
            [(0.425, 0.56), (225, 530)],
            ["Middle cell under lateral load", "Lowest natural frequency"],
            [r"Centre travel [$\mu$m/N]", "Frequency [Hz]"],
            [".4f", ".1f"],
            strict=True,
        )
    ):
        ax.scatter(ref[k], 3, marker="D", s=20, color="#555555", label="Bare control", zorder=3)
        ax.annotate(
            format(ref[k], fmt),
            (ref[k], 3),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
        )
        for j, variant in enumerate(pairs):
            seated, opened = variant[k]
            y = 2 - j
            ax.plot([seated, opened], [y, y], color="#aaa", lw=1.15)
            for value, color, marker, description in [
                (seated, "#08357E", "o", "At bolt lock"),
                (opened, "#38761D", "s", "Pocket held open"),
            ]:
                ax.scatter(
                    value,
                    y,
                    marker=marker,
                    s=24,
                    facecolors=color if marker == "o" else "white",
                    edgecolors=color,
                    zorder=3,
                    label=description if j == 0 else None,
                )
                on_right = value == max(seated, opened)
                ax.annotate(
                    format(value, fmt),
                    (value, y),
                    xytext=(5 if on_right else -5, 0),
                    textcoords="offset points",
                    ha="left" if on_right else "right",
                    va="center",
                    fontsize=8,
                    color=color,
                )
        ax.set(
            xlim=xlim,
            ylim=(-0.35, 3.45),
            yticks=[3, 2, 1, 0],
            yticklabels=labels,
            title=title,
            xlabel=unit,
        )
        ax.tick_params(axis="y", length=0)
        ax.spines[["top", "left", "right"]].set_visible(False)
        ax.grid(axis="x", alpha=0.13)
    fig.legend(
        *axes[0].get_legend_handles_labels(),
        loc="outside lower center",
        frameon=False,
        ncol=3,
        fontsize=9,
    )
    fig.savefig(
        ROOT / "docs/figures/snug-middle-pocket-release.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


if __name__ == "__main__":
    draw()

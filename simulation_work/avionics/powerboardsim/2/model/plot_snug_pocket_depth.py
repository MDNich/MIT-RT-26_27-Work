"""Compare overlap on the FE and STEP surfaces at the same aluminium-mount displacements."""

import numpy as np
from film_identity import verified
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read


def draw():
    depth = read(AUDIT / "aluminium_curved_pocket_depth.json")
    verified(AUDIT / "aluminium_unilateral_startup.json", depth["startup_sha256"])
    fig, axes = plt.subplots(1, 2, sharey=True, figsize=(8.0, 2.32), layout="constrained")
    keys = ["static_8", *(f"{a}_peak_spring_opening" for a in "XYZ")]
    labels = ["Bolt lock", "Base X", "Base Y", "Base Z"]
    handles = []
    for ax, site, title in zip(
        axes, ("original", "second"), ("Initially loaded PLA face", "Second PLA face"), strict=True
    ):
        ax.axhline(0, linewidth=0.7, color="#444444", zorder=1)
        for method, offset, color, marker, label in [
            ("FE", -0.13, "#08357E", "o", "Quadratic mesh"),
            ("CAD_at_same_displacements", 0.13, "#38761D", "D", "STEP curvature"),
        ]:
            spans = np.array([depth["stations"][k][site]["depth_nm_interval"][method] for k in keys])
            assert np.max(np.ptp(spans, axis=1)) <= depth["interval_tolerance_nm"]
            y = spans.mean(axis=1)
            x = np.arange(len(y)) + offset
            pts = ax.scatter(x, y, s=24, marker=marker, color=color, zorder=3, label=label)
            if ax is axes[0]:
                handles.append(pts)
            for px, py in zip(x, y, strict=True):
                ax.annotate(
                    rf"({py:+.0f})",
                    (px, py),
                    xytext=(-2 if offset < 0 else 2, 4),
                    textcoords="offset points",
                    ha="right" if offset < 0 else "left",
                    color=color,
                    fontsize=8,
                )
        ax.set(title=title, xticks=np.arange(4), xticklabels=labels, ylim=(-49, 92), xlim=(-0.56, 3.57))
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.12)
    axes[0].set_ylabel("Signed overlap [nm]")
    fig.legend(handles=handles, loc="outside lower center", ncol=2, frameon=False, fontsize=9)
    fig.savefig(
        ROOT / "docs/figures/snug-aluminium-pocket-curvature.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


if __name__ == "__main__":
    draw()

"""Plot the force-controlled side load on the complete bare board."""

from film_identity import digest
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read


def draw():
    path = AUDIT / "bare_cellpush_x.json"
    direct = read(path)
    stresses = read(AUDIT / "bare_cellpush_x_stresses.json")
    assert stresses["direct_pull_audit_sha256"] == digest(path)
    rows = [r for r in direct["states"] if 3 <= r["time"] <= 5]
    stress = {r["native_set"]: r for r in stresses["states"]}
    nickel = [stress[r["native_set"]]["metrics"]["nickel_equivalent_MPa"]["all"] for r in rows]
    force = [r["applied_X_N"] for r in rows]
    fig, (motion, metal) = plt.subplots(1, 2, figsize=(8.6, 2.9), layout="constrained")
    blue, green = "#08357E", "#38761D"
    for ax, series in (
        (motion, [(r"To board supports", [r["cell_centres_XYZ_um"][0][0] for r in rows]),
                  (r"To the two clamps", [r["left_to_clamps_XYZ_um"][0] for r in rows])]),
        (metal, [(r"Largest rise at any one site", [s["largest_same_site_rise"]["value"] for s in nickel]),
                 (r"Rise in overall maximum", [s["largest_total"]["value"] - nickel[0]["largest_total"]["value"] for s in nickel])]),
    ):
        for (label, values), color, marker in zip(series, (blue, green), ("o", "s"), strict=True):
            ax.plot(force, values, color=color, marker=marker, markersize=3.5, label=label)
        ax.set_xlabel(r"Sideways force on the left cell [N]")
        ax.set_xlim(-0.2, 9.0)
        ax.set_xticks([0, 2, 4, 6, 8])
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", lw=0.45, color="#dddddd")
        ax.legend(loc="upper left", frameon=False, fontsize=8.5)
    motion.set_title(r"Left-cell travel", loc="left", fontsize=11, color=blue)
    motion.set_ylabel(r"Displacement along PCB X [$\mu$m]")
    metal.set_title(r"Stress in the six nickel strips", loc="left", fontsize=11, color=blue)
    metal.set_ylabel(r"Increase in equivalent stress [MPa]")
    fig.savefig(ROOT / "docs/figures/bare-board-side-load.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


if __name__ == "__main__":
    draw()

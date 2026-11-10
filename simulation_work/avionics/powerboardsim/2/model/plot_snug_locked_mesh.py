"""Compare bolt-lock displacement and middle-pocket force as the printed case mesh is refined."""

import numpy as np
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read


def draw():
    fig, (board, pocket) = plt.subplots(1, 2, figsize=(7.9, 2.65), layout="constrained")
    bare = None
    levels = [0, 1]
    for material, color in (("nylon", "#08357E"), ("aluminium", "#38761D")):
        runs = read(AUDIT / f"{material}_force_mesh_comparison.json")["runs"]
        assert [r["mesh_size_mm"] for r in runs] == [2.0, 1.5]
        for run in runs:
            name = run["case"]
            model = read(ROOT / "validation/static" / f"{name}.json")["models"]["bare_static"]
            if bare is None:
                bare = model
            assert bare == model and run["bare_sha256"] == model["source_rst_sha256"]
            load = read(AUDIT / f"{name}_load_path.json")
            assert load["rst_sha256"] == run["rst_sha256"]
            final = load["states"][-1]
            assert final["time"] == 2 and final["within_existing_bearing_force_screens"]
            np.testing.assert_allclose(np.linalg.norm(final["native_contact_resultant_XYZ_N"]), run["locked_resultant_N"], atol=1e-9)
        for ax, values, digits in (
            (board, [r["peak_final_U_um"]["pcb"] for r in runs], 2),
            (pocket, [r["locked_resultant_N"] for r in runs], 4 if material == "aluminium" else 3),
        ):
            ax.plot(levels, values, "-o" if material == "nylon" else "-s", color=color, label=material.capitalize(), ms=4)
            for x, value in zip(levels, values, strict=True):
                offset = -12 if ax is board and material == "aluminium" else 6
                ax.annotate(f"{value:.{digits}f}", (x, value), xytext=(0, offset), textcoords="offset points", ha="center", fontsize=8)
    peak = 1000 * bare["scopes"]["pcb"]["peak_total_U_mm"]
    board.axhline(peak, color="#555555", ls="--", label="Bare PCB", lw=1)
    board.text(0.5, peak + 0.8, f"{peak:.2f}", color="#444444", ha="center", fontsize=8)
    board.set(title="Peak PCB displacement", ylabel=r"Displacement [$\mu$m]", ylim=(0, 55))
    pocket.set(title="Middle-cell contact at bolt lock", ylabel="Resultant force [N]", yscale="log", ylim=(0.009, 1.35))
    ticks = [0.01, 0.03, 0.1, 0.3, 1]
    pocket.set_yticks(ticks, labels=["0.01", "0.03", "0.1", "0.3", "1"])
    for ax in (board, pocket):
        ax.set(xlim=(-0.22, 1.22), xticks=levels, xticklabels=["2 mm", "1.5 mm"], xlabel="Case mesh size")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.22)
        ax.set_axisbelow(True)
    fig.legend(*board.get_legend_handles_labels(), loc="outside lower center", ncols=3, frameon=False)
    fig.savefig(ROOT / "docs/figures/snug-locked-mesh.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


if __name__ == "__main__":
    draw()

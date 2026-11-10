"""Compare the board-normal response for the two assumed M4 assembly states."""

import numpy as np
from film_identity import digest
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read


def draw():
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 2.65), sharey=True, layout="constrained")
    labels = ["Nylon, 2 mm", "Nylon, 1.5 mm", "Aluminium, 2 mm"]
    for i, branch in enumerate(("snug125_nylon", "snug125_nylon_mesh15", "snug125_aluminium")):
        original_path = AUDIT / f"{branch}_open_pocket_level.json"
        original = read(original_path)
        data = read(AUDIT / f"{branch}_preloaded_vibration.json")
        static = AUDIT / f"{branch}_screw_preload_path.json"
        assert data["screw_preload_sha256"] == digest(static)
        assert original["modal_rst_sha256"] == data["native_basis_sha256"]
        baseline = original["axes"]["Z"]
        assert baseline["input_sha256"] == data["input_sha256"]
        tightened = data["methods"][data["selected"]]["open_point_check"]
        original_event = baseline["contact_witness"] or baseline["previous_monitored_change"]
        before = (
            original_event["stationary_rms_g"] * 1000,
            baseline["reference_input_startup"]["first_time_bracket_ms"][-1],
        )
        after = (
            tightened["lowest_level_bracket_rms_g"][-1] * 1000,
            tightened["reference_input_startup"]["first_time_bracket_ms"][-1],
        )
        y = 2 - i
        for ax, left, right in zip(axes, before, after, strict=True):
            ax.plot([left, right], [y + 0.12, y - 0.12], color="#ADB3BF", linewidth=0.8, zorder=1)
            for x, level, marker, color, title in (
                (left, y + 0.12, "o", "#08357E", "M4 shanks initially stress-free"),
                (right, y - 0.12, "D", "#8B251A", "Tightened to 1 N mean shank tension"),
            ):
                ax.plot(
                    x,
                    level,
                    marker=marker,
                    color=color,
                    ls="none",
                    ms=4.4,
                    zorder=2,
                    label=title if i == 0 else None,
                )
                ax.annotate(
                    f"{x:.3g}",
                    (x, level),
                    xytext=(5, 0),
                    textcoords="offset points",
                    ha="left",
                    va="center",
                    color=color,
                    fontsize=8,
                )
    for ax in axes:
        ax.set_ylim(-0.4, 2.4)
        ax.set_yticks([2, 1, 0], labels)
        ax.grid(axis="x", color="#dddddd", lw=0.5)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
    ax, t = axes
    ax.set_xscale("log")
    ax.set_xlim(0.22, 15)
    ax.set_xticks([0.3, 1, 3, 10], ["0.3", "1", "3", "10"])
    ax.set_title("Input level for the first contact change", loc="left", fontsize=10, color="#08357E")
    ax.set_xlabel(r"Stationary input [$10^{-3}\,g$ RMS]")
    t.set_xlim(0, 7.6)
    t.set_xticks(np.arange(0, 8, 2))
    t.set_title(r"First change under the full $14.14\,g$ input", loc="left", fontsize=10, color="#08357E")
    t.set_xlabel("Time from start [ms]")
    fig.legend(
        *ax.get_legend_handles_labels(), loc="outside lower center", ncols=2, frameon=False, fontsize=9
    )
    fig.savefig(
        ROOT / "docs/figures/snug-screw-vibration.pdf", metadata={"CreationDate": None, "ModDate": None}
    )
    plt.close(fig)


if __name__ == "__main__":
    draw()

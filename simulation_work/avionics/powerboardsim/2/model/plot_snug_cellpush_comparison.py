"""Compare the closed, force-controlled complete-board pulls at the shared load."""

import argparse

import numpy as np
from film_identity import digest
from report_plot import plt
from snug_board_pull import AUDIT, BRANCHES, ROOT, read


def draw(branches):
    fig, (travel, pressure) = plt.subplots(1, 2, figsize=(8.6, 2.65), layout="constrained")
    labels = {"bare": "Bare", "snug125_nylon": "Nylon", "snug125_aluminium": "Aluminium"}
    colors = {"snug125_nylon": "#38761D", "snug125_aluminium": "#08357E"}
    specs = read(AUDIT / "whole_board_pull_inputs.json")
    bare = specs["bare_cellpush_x"]
    for i, branch in enumerate(branches):
        case = branch + "_cellpush_x"
        proof = AUDIT / (case + ".json")
        history = read(proof)
        spec = specs[case]
        assert spec["force_cards_sha256"] == bare["force_cards_sha256"]
        rows = [r for r in history["states"] if 3 <= r["time"] <= 5]
        end = rows[-1]
        assert end["time"] == 5 and abs(end["applied_X_N"] - bare["endpoint_force_N"]) < 1e-10
        for v, offset, color, marker, name in (
            (end["cell_centres_XYZ_um"][0][0], 0.13, "#08357E", "o", "To board supports"),
            (end["left_to_clamps_XYZ_um"][0], -0.13, "#38761D", "s", "To strip clamps"),
        ):
            y = len(branches) - 1 - i + offset
            travel.plot(v, y, color=color, marker=marker, ms=4.2, label=name if i == 0 else None)
            travel.annotate(
                f"{v:.3f}",
                (v, y),
                xytext=(5, 0),
                textcoords="offset points",
                va="center",
                fontsize=8.5,
            )
        if branch != "bare":
            seats = read(AUDIT / (case + "_seats.json"))
            assert seats["native_pull_sha256"] == digest(proof)
            assert not set(seats["states_outside_force_screens"]) & {r["native_set"] for r in rows}
            vals = [
                r["middle_patch_comparison"]["native_whole_case_projected_compression_N"] for r in rows
            ]
            pressure.plot(
                [r["applied_X_N"] for r in rows],
                vals,
                "-o",
                color=colors[branch],
                lw=1.3,
                ms=3.1,
                label=labels[branch] + " screws",
            )
    travel.set_title("Left-cell travel at 8.542 N", loc="left", color="#08357E", fontsize=11)
    travel.set_yticks(range(len(branches)), [labels[b] for b in branches[::-1]])
    travel.set_ylim(-0.55, len(branches) - 0.45)
    travel.set(xlabel=r"Displacement along PCB X [$\mu$m]", xlim=(0, 5.65))
    travel.legend(loc="lower left", frameon=False, ncol=2, fontsize=8)
    pressure.set_title("Force at the middle pocket", loc="left", color="#08357E", fontsize=11)
    pressure.set(
        xlabel="Sideways force on the left cell [N]",
        ylabel="Projected compression [N]",
        xlim=(-0.2, 9),
        ylim=(0, None),
    )
    pressure.set_xticks(np.arange(0, 9, 2))
    pressure.legend(loc="lower left", frameon=False, fontsize=8)
    for axis in (travel, pressure):
        axis.spines[["right", "top"]].set_visible(False)
        axis.grid(axis="x", lw=0.45, color="#ddd")
        axis.set_axisbelow(True)
    fig.savefig(
        ROOT / "docs/figures/snug-board-side-load.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branches", nargs="+", choices=BRANCHES)
    args = parser.parse_args()
    assert tuple(args.branches) in (BRANCHES[:2], BRANCHES)
    draw(args.branches)

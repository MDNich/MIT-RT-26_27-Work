"""Compare the closed, force-controlled complete-board pulls at the shared load."""

import argparse

import numpy as np
from film_identity import digest
from report_plot import plt
from snug_board_pull import AUDIT, BRANCHES, ROOT, read


def draw(branches):
    fig, axes = plt.subplots(
        1,
        len(branches),
        figsize=(8.6, 2.65),
        layout="constrained",
        width_ratios=[1.35, *([1] * (len(branches) - 1))],
    )
    travel = axes[0]
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
            pressure = axes[i]
            excluded = set(seats["states_outside_force_screens"])
            scale = 1000 if branch == "snug125_aluminium" else 1
            unit = "mN" if scale == 1000 else "N"
            for states, style, marker, fill in (
                (rows, "-", "o", colors[branch]),
                ([r for r in history["states"] if r["time"] >= 5], "--", "s", "none"),
            ):
                force = [r["applied_X_N"] for r in states]
                vals = (
                    np.asarray(
                        [
                            r["middle_patch_comparison"]["native_whole_case_projected_compression_N"]
                            for r in states
                        ]
                    )
                    * scale
                )
                passed = np.array([r["native_set"] not in excluded for r in states])
                pressure.plot(
                    force,
                    np.where(passed, vals, np.nan),
                    ls=style,
                    marker=marker,
                    color=colors[branch],
                    mfc=fill,
                    ms=3.7,
                    lw=1,
                    label="Loading" if style == "-" else "Unloading",
                )
                if not all(passed):
                    pressure.scatter(
                        np.array(force)[~passed], vals[~passed], color="#7A0101", s=18, marker="x"
                    )
            pressure.set_title(
                labels[branch] + " middle pocket", loc="left", color="#08357E", fontsize=10.5
            )
            pressure.set(
                xlabel="Left-cell load [N]", ylabel=f"Compression [{unit}]", xlim=(-0.25, 9.1)
            )
            pressure.set_xticks(np.arange(0, 9, 2))
            pressure.set_ylim(bottom=min(pressure.get_ylim()[0], -0.035 * max(pressure.get_ylim()[1], 1e-4)))
            pressure.legend(loc="best", frameon=False, fontsize=7.8)
    travel.set_title("Left-cell travel at 8.542 N", loc="left", color="#08357E", fontsize=11)
    travel.set_yticks(range(len(branches)), [labels[b] for b in branches[::-1]])
    travel.set_ylim(-1.0, len(branches) - 0.45)
    travel.set(xlabel=r"Displacement along PCB X [$\mu$m]", xlim=(0, 5.65))
    travel.legend(loc="lower left", frameon=False, ncol=1, fontsize=7.2)
    for axis in axes:
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

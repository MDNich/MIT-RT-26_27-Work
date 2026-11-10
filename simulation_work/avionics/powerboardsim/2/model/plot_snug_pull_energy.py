"""Compare work at common load and common travel in the bare and snug forward pulls."""

import numpy as np
from film_identity import verified
from report_plot import plt
from snug_board_pull import ROOT, read
from snug_pull_steps import ENERGY, PARENT
from stage_snug_fit import AUDIT


def draw():
    record = read(ENERGY)
    verified(AUDIT / f"{PARENT}_ls3_ss47_checkpoint.json", record["checkpoint_sha256"])
    histories = record["cased"]["history"]
    (index,) = np.flatnonzero([r["native_set"] == 21 for r in histories])
    cased = histories[index]
    assert cased["within_parent_screens"]
    atforce = record["at_bare_endpoint_force"]
    work = cased["actuator_work_mJ"]
    bare = record["bare_work_at_cased_stations"][index]["external_work_mJ"]
    fig, (match, nickel, parts) = plt.subplots(
        1, 3, figsize=(8.3, 2.5), layout="constrained", gridspec_kw={"width_ratios": [1.15, 0.93, 1.06]}
    )
    navy = "#08357E"
    green = "#38761D"
    data = [
        (atforce["external_work_mJ"], record["bare"]["history"][-1]["actuator_work_mJ"]),
        (work, bare),
    ]
    match.set(
        xscale="log",
        xlim=(0.030, 20),
        ylim=(-0.42, 1.39),
        yticks=[1, 0],
        yticklabels=["8.54 N", "0.207 mm"],
        xlabel="Actuator work [mJ]",
        title="Matched loading",
    )
    match.hlines(1, *atforce["endpoint_work_bracket_mJ"], color=green, lw=4, alpha=0.35)
    for i, (snug, reference) in enumerate(data):
        y = 1 - i
        match.plot([snug, reference], [y, y], color="#aaa", lw=0.8, zorder=0)
        for val, mark, color, label in [
            (snug, "D", green, "Snug nylon"),
            (reference, "o", navy, "Bare"),
        ]:
            match.scatter(
                val, y, marker=mark, s=26, color=color, label=label if i == 0 else None, zorder=3
            )
            match.annotate(
                f"{val:.3g}",
                (val, y),
                xytext=(0, 5),
                textcoords="offset points",
                ha="center",
                va="bottom",
                color=color,
                fontsize=9,
            )
    match.set_xticks([0.1, 1, 10], labels=["0.1", "1", "10"])
    match.legend(ncol=2, loc="lower center", bbox_to_anchor=(0.5, 0.34), frameon=False, fontsize=8)
    evidence = read(AUDIT / "nickel_initiation_replay.json")
    replay = evidence["matched_bilinear"]
    proof = read(AUDIT / f"{PARENT}_ls3_ss24_checkpoint.json")
    assert (
        proof["rst_sha256"] == replay["snug_rst_sha256"]
        and proof["bare_rst_sha256"] == replay["bare_rst_sha256"]
    )
    np.testing.assert_allclose(
        replay["common_load_N"],
        proof["equal_bare_endpoint_load"]["bare"]["cell_force_N"],
        rtol=0,
        atol=1e-8,
    )
    at_load = [
        replay["snug"][k - 1]["curves"]["0.3"]["maximum"] for k in replay["snug_common_load_bracket"]
    ]
    assert at_load == [0.0, 0.0]
    (case_at_travel,) = [r for r in replay["snug"] if r["native_set"] == cased["native_set"]]
    travel = case_at_travel["travel_mm"]
    assert abs(travel - 0.206875) < 1.0e-8
    bare_states = replay["bare"]
    upper = next(i for i, row in enumerate(bare_states) if row["travel_mm"] >= travel)
    pair = bare_states[upper - 1 : upper + 1]
    bare_limits = [100 * r["curves"]["0.3"]["maximum"] for r in pair]
    bare_value = np.interp(travel, [r["travel_mm"] for r in pair], bare_limits)
    snug_value = 100 * case_at_travel["curves"]["0.3"]["maximum"]
    nickel.set(
        ylim=match.get_ylim(),
        xlim=(-0.45, 7.2),
        yticks=[1, 0],
        yticklabels=[],
        xticks=[0, 2, 4, 6],
        xlabel="Initiation criterion [\\%]",
        title="Nickel strip history",
    )
    nickel.hlines(0, *bare_limits, color=navy, lw=4, alpha=0.35)
    for y, first, second in [
        (1, 0.0, 100 * bare_states[-1]["curves"]["0.3"]["maximum"]),
        (0, snug_value, bare_value),
    ]:
        nickel.hlines(y, min(first, second), max(first, second), color="#aaa", lw=0.8)
        for val, mark, color, offset in (
            (first, "D", green, 6),
            (second, "o", navy, 6 if y == 1 else -13),
        ):
            nickel.plot(val, y, marker=mark, ms=4.2, color=color)
            nickel.annotate(
                f"{val:.2f}",
                (val, y),
                xytext=(0, offset),
                textcoords="offset points",
                ha="center",
                color=color,
                fontsize=8,
            )
    group = cased["work_by_group_mJ"]
    values = [
        group["PLA"],
        group["shanks"],
        group["nickel"],
        sum(group[k] for k in group if k not in ("PLA", "shanks", "nickel")),
    ]
    for y, (value, color) in enumerate(zip(values, [navy, "#3C78D8", green, "#5A43A0"], strict=True)):
        parts.barh(3 - y, value, height=0.48, color=color)
        parts.text(value + 0.08, 3 - y, f"{value:.2f}", va="center", fontsize=8)
    parts.set(
        yticks=[3, 2, 1, 0],
        yticklabels=["Printed case", "Four shanks", "Nickel strips", "Other elements"],
        xlabel="Nodal-force work [mJ]",
        title="Snug fixture at 0.207 mm",
        xlim=(0, 5.9),
    )
    for ax in (match, nickel, parts):
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", alpha=0.12)
    fig.savefig(
        ROOT / "docs/figures/snug-pull-work.pdf", metadata={"CreationDate": None, "ModDate": None}
    )
    plt.close(fig)


if __name__ == "__main__":
    draw()

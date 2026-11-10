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
    fig, (match, parts) = plt.subplots(
        1, 2, figsize=(8.2, 2.45), layout="constrained", gridspec_kw={"width_ratios": [1.2, 1]}
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
        xlabel="Work done by the actuator [mJ]",
        title="Match the force or the travel",
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
        xlabel="Integrated nodal-force work [mJ]",
        title="Snug fixture at 0.207 mm",
        xlim=(0, 5.9),
    )
    for ax in (match, parts):
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", alpha=0.12)
    fig.savefig(
        ROOT / "docs/figures/snug-pull-work.pdf", metadata={"CreationDate": None, "ModDate": None}
    )
    plt.close(fig)


if __name__ == "__main__":
    draw()

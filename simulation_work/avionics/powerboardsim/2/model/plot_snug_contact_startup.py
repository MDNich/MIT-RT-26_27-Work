"""Publish matched cell motion and middle-pocket compression during base-Z startup."""

import numpy as np
from film_identity import verified
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read
from snug_contact_vibration import CACHE


def draw():
    summary = read(AUDIT / "matched_contact_startup.json")
    cache = CACHE / "matched_contact_startup.npz"
    verified(cache, summary["history_sha256"])
    tick = summary["axes"]["Z"]["time_ms"]
    data = np.load(cache)
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.15, 2.75), layout="constrained")
    for key, label, color, ls in (
        ("bare", "Bare board", "#444444", ":"),
        ("snug125_nylon", "Nylon, 2 mm", "#08357E", "-"),
        ("snug125_nylon_mesh15", "Nylon, 1.5 mm", "#3C78D8", "--"),
        ("snug125_aluminium", "Aluminium, 2 mm", "#38761D", "-"),
    ):
        if key != "bare":
            a.plot(data["time_ms"], data["Z_" + key + "_force"], color=color, ls=ls, lw=1.1)
        b.plot(data["time_ms"], data["Z_" + key], color=color, ls=ls, lw=1.15, label=label)
    a.set(title="Middle pocket", ylabel="Sum of compressive forces [N]", ylim=(0, None))
    b.set(title="Middle cell relative to the base", ylabel=r"Cell-centre Z travel [$\mu$m]")
    for ax in (a, b):
        ax.axvline(tick, color="#5A43A0", lw=0.8, ls="-.", alpha=0.85)
        ax.set(xlim=(0, 31.25), xticks=[0, 5, 10, 15, 20, 25, 30], xlabel="Time in base-Z record [ms]")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.13)
    fig.legend(
        *b.get_legend_handles_labels(), loc="outside lower center", frameon=False, ncol=4, fontsize=8.2
    )
    fig.savefig(
        ROOT / "docs/figures/snug-coupled-startup.pdf", metadata={"CreationDate": None, "ModDate": None}
    )
    plt.close(fig)
    data.close()


if __name__ == "__main__":
    draw()

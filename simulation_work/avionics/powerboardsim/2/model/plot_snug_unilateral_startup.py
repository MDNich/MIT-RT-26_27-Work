"""Show local contact force and opening in the first aluminium vibration cycle."""

import numpy as np
from film_identity import verified
from report_plot import plt
from snug_pocket_dynamics import BASIS_PROOF, OUTPUT, ROOT, STUDY, read


def draw():
    study = read(STUDY)
    verified(BASIS_PROOF, study["basis_audit_sha256"])
    basis = OUTPUT / "reduction.npz"
    verified(basis, read(BASIS_PROOF)["basis_sha256"])
    with np.load(basis) as data:
        stiffness = float(data["beta"]) ** 2
    fig, (force, opening) = plt.subplots(1, 2, figsize=(8.15, 2.55), layout="constrained")
    for axis, color, style in zip(
        "XYZ", ["#38761D", "#5A43A0", "#08357E"], ["-.", "--", "-"], strict=True
    ):
        row = study["axes"][axis]
        path = OUTPUT / f"{axis}_response.npz"
        verified(path, row["history_sha256"])
        with np.load(path) as data:
            t = data["time_s"] * 1000
            compression = data["preload_N"] - data["opening_increment_N"]
            onset, reload = [1000 * e["time_s"] for e in row["exact_state_transitions"][:2]]
            keep = (t >= onset) & (t <= reload)
            gap = -compression[keep] / stiffness * 1e9
            np.testing.assert_allclose(gap.max(), 1000 * row["first_cycle"]["peak_opening_um"])
            opening.plot(
                np.r_[0, t[keep] - onset, reload - onset],
                np.r_[0, gap, 0],
                style,
                color=color,
                lw=1.6,
                label=rf"Base {axis} ({gap.max():.1f} nm)",
            )
            peak = int(np.argmax(gap))
            opening.annotate(
                f"{axis}: {gap[peak]:.1f} nm",
                (t[keep][peak] - onset, gap[peak]),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                color=color,
                fontsize=8,
            )
            if axis == "Z":
                force.axhline(0, color="#444444", linewidth=0.65)
                force.axvspan(onset, reload, color="#3C78D8", alpha=0.12)
                force.plot(
                    data["native_frozen_time_s"] * 1000,
                    1000 * (data["preload_N"] - data["native_frozen_increment_N"]),
                    "--",
                    lw=1.3,
                    color="#7A0101",
                    label="Fixed contact",
                )
                force.plot(
                    t, 1000 * np.maximum(compression, 0), color=color, lw=1.6, label="Opening allowed"
                )
    force.set(
        xlim=(5.3, 6.36),
        xlabel="Time from vibration start [ms]",
        ylabel="Normal compression [mN]",
        title="Middle pocket under base Z",
    )
    # Autoscale to the local window; later cycles have much larger loads.
    ys = [
        line.get_ydata()[(line.get_xdata() >= 5.3) & (line.get_xdata() <= 6.36)]
        for line in force.lines[1:]
    ]
    low, high = min(y.min() for y in ys), max(y.max() for y in ys)
    force.set_ylim(low - 0.08 * (high - low), high + 0.25 * (high - low))
    opening.set(
        xlim=(0, 0.56),
        ylim=(-1, 53),
        xlabel="Time since first release [ms]",
        ylabel="Local spring opening [nm]",
        title="First opening of the loaded contact",
    )
    for ax in (force, opening):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.13)
    force.legend(frameon=False, fontsize=8, loc="upper center")
    fig.savefig(
        ROOT / "docs/figures/snug-aluminium-first-opening.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


if __name__ == "__main__":
    draw()

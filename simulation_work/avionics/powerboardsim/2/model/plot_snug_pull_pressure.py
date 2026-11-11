"""Compare native pull forces and each cell's loaded area and peak pressure."""

import numpy as np
from audit_local import ROOT, read
from compare_pull import series
from compare_snug_middle_engagement import OUTPUT as MIDDLE, STEMS
from film_identity import digest, verified
from report_plot import plt
from snug_local_checkpoint import CASE
from stage_snug_fit import AUDIT


def draw():
    checkpoint = AUDIT / f"{CASE}_ls3_ss18_checkpoint.json"
    audit = read(AUDIT / f"{CASE}_ls3_ss18_cell_pressure.json")
    assert audit["checkpoint_sha256"] == digest(checkpoint)
    states = audit["states"]
    travel = np.array([s["travel_mm"] for s in states])
    comparison = read(MIDDLE)
    aluminium_path = AUDIT/f"{STEMS['aluminium']}_cell_pressure.json"
    verified(aluminium_path, comparison['sources']['aluminium']['pressure']['sha256'])
    aluminium = [s for s in read(aluminium_path)['states'] if s['native_set'] <= comparison['last_common_native_set']]
    assert [s['native_set'] for s in aluminium] == [s['native_set'] for s in states]
    _, bare = series(read(checkpoint)["bare_case"])
    fig, axes = plt.subplots(1, 3, figsize=(7.85, 2.68), layout="constrained")
    force, area, pressure = axes
    xmax = travel.max()
    left_bare = [r for r in bare if 0 < r["ux_mm"] <= xmax]
    positive = [s for s in states if s["actuator_N"] > 0 and s["travel_mm"] > 1e-6]
    force.semilogy(
        [s["travel_mm"] for s in positive],
        [s["actuator_N"] for s in positive],
        "o-",
        ms=2.8,
        lw=1.1,
        color="#08357E",
        label="Snug nylon",
    )
    force.semilogy(
        [r["ux_mm"] for r in left_bare],
        [r["cell_force_N"] for r in left_bare],
        "s--",
        ms=2.3,
        lw=1,
        color="#44444A",
        label="Bare",
    )
    force.semilogy([s['travel_mm'] for s in aluminium], [s['actuator_N'] for s in aluminium],
                   'o-', ms=2.8, lw=1.1, color='#7A0101', label='Snug aluminium')
    force.legend(loc="upper left", fontsize=8, frameon=False)
    for body, label, marker, color in [
        ("4", "Driven left", "o", "#08357E"),
        ("19", "Fixed middle", "D", "#38761D"),
        ("15", "Fixed right", "^", "#674EA7"),
    ]:
        loaded = [s for s in states if body in s["cells"]]
        for ax, key in [(area, "contact_area_mm2")]:
            ax.plot(
                [s["travel_mm"] for s in loaded],
                [s["cells"][body][key] for s in loaded],
                lw=1.2,
                ms=3.8,
                marker=marker,
                color=color,
                label=label,
            )
    for material, rows, color in [('Nylon', states, '#38761D'), ('Aluminium', aluminium, '#7A0101')]:
        for body, role, marker, line in [('4', 'left', 'o', '-'), ('19', 'middle', 'D', '--')]:
            loaded = [s for s in rows if body in s['cells']]
            pressure.plot([s['travel_mm'] for s in loaded], [s['cells'][body]['peak_pressure_MPa'] for s in loaded],
                          lw=1.2, ms=3.8, marker=marker, linestyle=line, color=color, label=material+', '+role)
    pressure.legend(loc='upper left', fontsize=6.9, frameon=False, labelspacing=.2)
    cad = read(AUDIT / "moving_cell_target_resolution.json")
    assert cad["pressure_sha256"] == digest(AUDIT / f"{CASE}_ls3_ss18_cell_pressure.json")
    assert [s["native_set"] for s in states] == [s["native_set"] for s in cad["states"]]
    overlaps = [s for s in cad["states"] if s["exact_CAD_inside_points"]]
    area.plot(
        [s["travel_mm"] for s in overlaps],
        [s["CAD_inside_point_area_mm2"] for s in overlaps],
        ls="--",
        marker="s",
        ms=3.2,
        mfc="white",
        lw=1.0,
        color="#7A0101",
        label="Left, STEP overlap",
    )
    area.legend(loc="lower left", fontsize=7.1, frameon=False, labelspacing=0.2)
    for ax, title, ylabel in zip(
        axes,
        ("Force to move the cell", "Nylon: contact and overlap", "Driven and middle cells"),
        ("Applied force [N]", r"Area [mm$^2$]", "Pressure [MPa]"),
        strict=True,
    ):
        ax.set(
            ylabel=ylabel,
            xlabel="Left-cell travel [mm]",
            xlim=(0, xmax + 0.010),
            xticks=[0, 0.05, 0.10, 0.15, 0.20],
        )
        ax.set_title(title, loc="left", fontsize=10, color="#08357E", pad=6)
        ax.tick_params(labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#DADADA", lw=0.45)
        ax.set_axisbelow(True)
    area.set_ylim(0, 1.06 * max(s["CAD_inside_point_area_mm2"] for s in overlaps))
    pressure.set_ylim(0, 1.12*max(g['peak_pressure_MPa'] for s in aluminium+states for g in s['cells'].values()))
    fig.savefig(
        ROOT / "docs/figures/snug-pull-pressure.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


if __name__ == "__main__":
    draw()

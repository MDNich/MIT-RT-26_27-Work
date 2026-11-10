"""Plot native and independently integrated PCB spectra and the two PLA mesh comparisons."""

import numpy as np
from installation_material import PLA
from raised_spectrum_comparison import axis_results
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read

MOUNTS = (("nylon", "#3C78D8", "s"), ("aluminium", "#38761D", "^"))


def format_axis(ax, title, ylabel):
    ax.set(title=title, ylabel=ylabel, xticks=range(3), xticklabels=["Base X", "Base Y", "Base Z"])
    ax.set_ylim(bottom=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)


def spectra():
    nominal = {a: axis_results(a, "snug125") for a in "XYZ"}
    fig, axes = plt.subplots(1, 2, figsize=(8.25, 2.8), layout="constrained")
    x = np.arange(3)
    for ax, metric in zip(axes, ("pcb_Z_displacement_um", "pcb_equivalent_stress_MPa"), strict=True):
        ax.scatter(x-0.28, [nominal[a]["bare"][metric] for a in "XYZ"], color="#08357E", s=32, label="Bare")
    for index, (material, color, marker) in enumerate(MOUNTS):
        branch = "snug125_" + material
        modal = read(AUDIT / f"{material}_modal_mesh_comparison.json")
        stress = read(AUDIT / f"{material}_mesh_pcb_spectra.json")
        assert modal["models"][1]["basis_rst_sha256"] == stress["fine_basis_rst_sha256"]
        for axis in "XYZ":
            assert stress["axes"][axis]["nominal_native_rst_sha256"] == nominal[axis][branch]["rst_sha256"]
        values = (
            [modal["independent_RMS_displacements"][a]["pcb"]["fine_peak_XYZ_um"][2] for a in "XYZ"],
            [stress["axes"][a]["fine_cutoffs_Hz"]["4000"]["peak_MPa"] for a in "XYZ"],
        )
        for ax, fine, metric in zip(axes, values, ("pcb_Z_displacement_um", "pcb_equivalent_stress_MPa"), strict=True):
            pos = x - 0.13 + 0.30 * index
            ax.scatter(pos, [nominal[a][branch][metric] for a in "XYZ"], marker=marker, color=color, s=35,
                       label=f"{material.capitalize()}, 2 mm")
            ax.scatter(pos+0.12, fine, marker=marker, facecolors="white", edgecolors=color, lw=1.4, s=37,
                       label=f"{material.capitalize()}, 1.5 mm")
    format_axis(axes[0], "Peak PCB Z displacement", r"Displacement [$\mu$m RMS]")
    format_axis(axes[1], "Peak PCB equivalent stress", "Stress [MPa RMS]")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center", ncols=5, fontsize=8, frameon=False)
    fig.savefig(ROOT / "docs/figures/snug-refined-spectra.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def through_layer():
    fig, axes = plt.subplots(1, 2, figsize=(8.25, 2.9), sharey=True, layout="constrained")
    x = np.arange(3)
    maximum = 100.0
    for ax, (material, _, _) in zip(axes, MOUNTS, strict=True):
        controls = read(AUDIT / f"{material}_modal_mesh_comparison.json")
        for i, model in enumerate(controls["models"]):
            branch = model["case"].removesuffix("_basis")
            all_nodes, away = [], []
            for axis in "XYZ":
                stem = f"{branch}_{axis}_PLA_"
                check = read(AUDIT / (stem + "exact.json"))
                response = read(AUDIT / (stem + "independent.json"))
                assert response["native_basis_sha256"] == check["native_basis_sha256"] == model["basis_rst_sha256"]
                assert response["input_sha256"] == check["input_sha256"]
                for scope, series in (("all", all_nodes), ("2mm_from_bearing", away)):
                    row = response["scopes"][scope]["layer_tension_MPa"]
                    exact = check["scopes"][scope]["layer_tension_MPa"]
                    assert row["coupon_reference_MPa"] == PLA["layer_tension_MPa"]
                    assert abs(exact["maximum_MPa"] / row["maximum_MPa"] - 1) < 0.005
                    series.append(row["percent_of_coupon_mean"])
            maximum = max(maximum, *all_nodes)
            pos = x + (i-0.5)*0.32
            color = ("#08357E", "#3C78D8")[i]
            ax.bar(pos, all_nodes, width=0.30, color=color, label=f"{model['mesh_size_mm']:g} mm case mesh")
            ax.scatter(pos, away, marker="_", color="white", s=62, linewidths=3, zorder=3)
            ax.scatter(pos, away, marker="_", color="#333333", s=56, linewidths=1, zorder=4)
        ax.axhline(100, color="#7A0101", ls="--", lw=1)
        format_axis(ax, f"{material.capitalize()} screws", r"Through-layer tension / coupon mean [\%]" if ax is axes[0] else "")
    axes[0].set_ylim(0, 1.12 * maximum)
    axes[0].plot([], [], marker="_", color="#333333", ls="none", label=r"At least 2 mm from bearing nodes")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center", ncols=3, fontsize=8, frameon=False)
    fig.savefig(ROOT / "docs/figures/snug-refined-layer-tension.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


if __name__ == "__main__":
    spectra()
    through_layer()

"""Compare pocket output and the reaction transmitted to the four mounting tabs during tightening."""

import numpy as np
from film_identity import digest
from report_plot import plt
from snug_board_pull import AUDIT, ROOT, read


def draw():
    reference = "snug125_nylon_out2_static"
    tighter = "snug125_nylon_tol001_static"
    pair = read(AUDIT / "nylon_force_tolerance_comparison.json")
    assert [r["case"] for r in pair["runs"]] == [reference, tighter]
    figures, axes = plt.subplots(1, 2, figsize=(8.65, 2.85), layout="constrained", sharex=True)
    for ax, source, title, run in zip(
        axes,
        (reference, tighter),
        ("Original force criterion", r"0.01 N force criterion"),
        pair["runs"],
        strict=True,
    ):
        path = read(AUDIT / (source + "_load_path.json"))
        bearing_file = AUDIT / (
            "snug125_nylon_installation_seats.json" if source == reference else source + "_seats.json"
        )
        assert path["bearing_sha256"] == digest(bearing_file)
        assert path["rst_sha256"] == run["rst_sha256"] and path["input_sha256"] == run["input_sha256"]
        rows = path["states"]
        x = [r["time"] for r in rows]
        assert x == run["times"] and x[-1] == 2
        pocket = [np.linalg.norm(r["native_contact_resultant_XYZ_N"]) for r in rows]
        tabs = [np.linalg.norm(r["solid_loads"]["four_tabs"]["force_XYZ_N"]) for r in rows]
        np.testing.assert_allclose(
            pocket, [r["resultant_N"] for r in run["force_history"]], atol=1e-9, rtol=1e-9
        )
        ax.plot(x, pocket, "-o", lw=1.25, ms=4.2, color="#08357E", label="Pocket contact")
        ax.plot(
            x,
            tabs,
            "--D",
            lw=1.2,
            ms=4.6,
            mfc="none",
            mew=1.1,
            color="#7A0101",
            label="Four-tab resultant",
        )
        ax.axvline(1, ls=":", color="#999999", lw=0.8)
        ax.set_title(title + " (2 mm mesh)", loc="left", fontsize=11, color="#08357E")
        ax.set(
            xlim=(0, 2.05),
            xticks=[0, 0.5, 1, 1.5, 2],
            ylabel="Resultant force [N]",
            xlabel="Static load-step parameter",
        )
        ax.set_ylim(bottom=-0.045 * max(pocket + tabs))
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#dddddd", lw=0.5)
        ax.set_axisbelow(True)
    if (AUDIT / "nylon_tight_mesh_comparison.json").is_file():
        mesh = read(AUDIT / "nylon_tight_mesh_comparison.json")
        assert mesh["runs"][0]["case"] == tighter
        fine = mesh["runs"][1]
        assert fine["case"] == "snug125_nylon_mesh15_tol001_static"
        verified_path = AUDIT / (fine["case"] + "_load_path.json")
        assert digest(verified_path) == fine["load_path_sha256"]
        path = read(verified_path)
        assert path["rst_sha256"] == fine["rst_sha256"]
        ax = axes[1]
        ax.lines[0].set_label("2 mm contact")
        ax.lines[1].set_label("2 mm tabs")
        x = [r["time"] for r in path["states"]]
        force = [np.linalg.norm(r["native_contact_resultant_XYZ_N"]) for r in path["states"]]
        tabs = [np.linalg.norm(r["solid_loads"]["four_tabs"]["force_XYZ_N"]) for r in path["states"]]
        ax.plot(x, force, "-s", color="#38761D", ms=4.2, lw=1.2, label="1.5 mm contact")
        ax.plot(x, tabs, "--D", color="#76549A", ms=5.6, mfc="none", mew=1, lw=1,
                label="1.5 mm tabs")
        ax.set_title("0.01 N criterion (both meshes)", loc="left", fontsize=11, color="#08357E")
        peak = max(force + tabs + [r["pocket_resultant_N"] for r in mesh["runs"][0]["states"]])
        ax.set_ylim(-0.045 * peak, 1.18 * peak)
        axes[0].legend(loc="upper right", frameon=False, fontsize=8)
        axes[1].legend(loc="upper left", frameon=False, fontsize=8)
    else:
        figures.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center",
                       ncols=2, frameon=False, fontsize=9)
    figures.savefig(
        ROOT / "docs/figures/snug-preload-convergence.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(figures)


if __name__ == "__main__":
    draw()

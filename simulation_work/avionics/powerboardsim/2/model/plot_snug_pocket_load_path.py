"""Plot the initial middle-cell force split and its transfer through the four mounts."""

import re

import numpy as np
from film_identity import digest, verified, write_json
from report_plot import plt
from snug_board_pull import AUDIT, CAMPAIGN, ROOT, read

BRANCHES = ("bare", "snug125_nylon", "snug125_nylon_mesh15", "snug125_aluminium")
LABELS = ("Bare", "Nylon", "Nylon, finer mesh", "Aluminium")
PILOTS = (950001, 950003, 950005, 950007)


def read_shares(branch):
    evidence = AUDIT / f"{branch}_initial_cell_load_paths.json"
    data = read(evidence)
    assert data["branch"] == branch and data["load_order"] == ["left", "middle", "right"]
    tangent = AUDIT / f"{branch}_full_board_tangent.json"
    verified(tangent, data["full_tangent_sha256"])
    paths = data["element_group_XYZ_N_per_N"]
    info = data["cell_load_paths"][1]
    assert info["material"] == 191
    native = ROOT / "validation/cell_attachment" / f"{branch}.json"
    native_data = read(native)
    assert native_data["modal_rst_sha256"] == data["modal_check"]["rst_sha256"]
    ends = sorted(native_data["spectrum"]["X"]["cells"]["191"]["ends"], key=lambda end: end["face_y_mm"])
    assert [end["pair"] for end in ends] == info["bond_pairs"]
    strips = [paths[f"strip {end['pair']}"][0][1] for end in ends]
    pocket = info["case_XYZ_N_per_N"][0]
    shares = np.array([*strips, pocket[1]])
    assert min(shares) >= 0 and abs(shares.sum() - 1) < 1e-8
    mounts = None
    if branch != "bare":
        mounts = -np.array([paths[f"mount {pilot}"][0][1] for pilot in PILOTS])
        assert min(mounts) > 0 and abs(mounts.sum() - pocket[1]) < 1e-8
        parent = branch + "_static"
        ledger = read(ROOT / ".runtime/receipts" / CAMPAIGN / parent / "archived.json")
        deck = ROOT / ".runtime/archive" / CAMPAIGN / parent / "model.inp"
        verified(deck, next(row["sha256"] for row in ledger["files"] if row["name"] == deck.name))
        records = re.findall(r"(?im)^N,(95000[1357]),([^,]+),([^,]+),[^\r\n]+$", deck.read_text())
        coords = {int(node): [float(x) * 1000, float(y) * 1000] for node, x, y in records}
        assert set(coords) == set(PILOTS)
        assert np.allclose(
            [coords[p] for p in PILOTS],
            [[3.18, 3.27], [3.18, 117.51], [66.04, 3.27], [66.04, 117.51]],
            atol=0.01,
        )
    return (
        shares,
        mounts,
        {
            "recovery_sha256": digest(evidence),
            "native_bonds_sha256": digest(native),
            "pocket_X_N_by_loaded_cell": pocket,
            "middle_end_Y_mm": [end["face_y_mm"] for end in ends],
        },
    )


def main():
    data = [read_shares(branch) for branch in BRANCHES]
    shares = 100 * np.stack([row[0] for row in data])
    mounts = 100 * np.stack([row[1] for row in data[1:]])
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(8.25, 2.75), layout="constrained", gridspec_kw={"width_ratios": [1.42, 1.0]}
    )
    y = np.arange(len(LABELS))[::-1]
    start = np.zeros(len(y))
    for values, color, label in zip(
        shares.T,
        ("#08357E", "#3C78D8", "#38761D"),
        ("Low-Y strip", "High-Y strip", "PLA pocket"),
        strict=True,
    ):
        left.barh(y, values, left=start, height=0.63, color=color, label=label)
        for pos, x0, value in zip(y, start, values, strict=True):
            if value > 0:
                left.text(
                    x0 + value / 2, pos, f"{value:.1f}", color="white", ha="center", va="center", fontsize=8
                )
        start += values
    left.set(
        yticks=y,
        yticklabels=LABELS,
        xlim=(0, 100),
        xlabel=r"Share of middle-cell X load [\%]",
        title="From the cell into the assembly",
    )
    left.legend(
        loc="upper center",
        bbox_to_anchor=(0.50, -0.29),
        ncol=3,
        columnspacing=0.9,
        fontsize=8,
        frameon=False,
    )
    x = np.arange(4)
    for offset, values, color, label in zip(
        (-0.23, 0, 0.23),
        mounts,
        ("#3C78D8", "#5A43A0", "#38761D"),
        ("Nylon", "Finer nylon", "Aluminium"),
        strict=True,
    ):
        right.bar(x + offset, values, width=0.22, color=color, label=label)
    right.set(
        xticks=x,
        xticklabels=["L, low Y", "L, high Y", "R, low Y", "R, high Y"],
        ylim=(0, 6),
        ylabel=r"Share of cell load [\%]",
        title="From the pocket into the four mounts",
    )
    right.tick_params(axis="x", labelsize=8)
    right.legend(
        loc="upper center",
        bbox_to_anchor=(0.50, -0.29),
        ncol=3,
        columnspacing=0.8,
        fontsize=8,
        frameon=False,
    )
    for ax in (left, right):
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_axisbelow(True)
    right.grid(axis="y", alpha=0.18)
    fig.savefig(
        ROOT / "docs/figures/snug-middle-load-path.pdf", metadata={"CreationDate": None, "ModDate": None}
    )
    plt.close(fig)
    write_json(
        AUDIT / "initial_cell_load_path_comparison.json",
        {
            "branch_order": BRANCHES,
            "inputs": {branch: row[2] for branch, row in zip(BRANCHES, data, strict=True)},
            "middle_load_pct_rows_by_branch_columns_low_Y_strip_high_Y_strip_PLA": shares.tolist(),
            "mount_X_pct_rows_by_cased_branch_columns_lowX_lowY_lowX_highY_highX_lowY_highX_highY": mounts.tolist(),
            "scope": "Independent incremental force in PCB X under a middle-cell load, with the installed contact state held fixed.",
        },
    )


if __name__ == "__main__":
    main()

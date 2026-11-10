"""Compare switch times at full input and input levels for the first monitored contact change."""

import numpy as np
from film_identity import digest, verified, write_json
from report_plot import plt
from seeded_motion import FS
from snug_board_pull import AUDIT, ROOT, read


def draw():
    names = ("snug125_nylon", "snug125_nylon_mesh15", "snug125_aluminium")
    fig, (time, level) = plt.subplots(1, 2, sharey=True, figsize=(8.2, 2.7), layout="constrained")
    results = {}
    for branch, title, marker, color, offset in zip(
        names,
        ("Nylon, 2 mm", "Nylon, 1.5 mm", "Aluminium, 2 mm"),
        ("o", "D", "^"),
        ("#08357E", "#38761D", "#7A0101"),
        (0.22, 0, -0.22),
        strict=True,
    ):
        path = AUDIT / f"{branch}_vibration_level.json"
        study = read(path)
        face_path = AUDIT / f"{branch}_pocket_face_unloading.json"
        spacer_path = AUDIT / f"{branch}_spacer_bearing.json"
        verified(face_path, study["pocket_audit_sha256"])
        verified(spacer_path, study["spacer_audit_sha256"])
        face, spacers = read(face_path), read(spacer_path)
        stress_path = AUDIT / f"{branch}_vibration_level_stress.json"
        stress = read(stress_path)
        assert stress["level_audit_sha256"] == digest(path)
        results[branch] = {"source_sha256": digest(path), "stress_sha256": digest(stress_path), "axes": {}}
        for idx, axis in enumerate("ZYX"):
            ax = study["axes"][axis]
            selected = ax["methods"][ax["selected"]]
            first = selected["first"]
            assert first["label"] == ax["first_with_exact_spacer_lengths"]["label"]
            levels = [m["first"]["scale"] for m in ax["methods"].values()]
            assert all(m["first"]["label"] == first["label"] for m in ax["methods"].values())
            source = face["axes"][axis]["selected"].removesuffix("_4000")
            p = face["axes"][axis]["histories"][source + "_4000"]["first_point_ms"]
            spans = spacers["axes"][axis]["integrations"][source]
            t = min([p] + [s["current_length"]["interpolated_ms"] for s in spans if s["current_length"]])
            g = first["stationary_rms_g"]
            mt = stress["axes"][axis]
            assert first["scale"] == mt["scale"]
            results[branch]["axes"][axis] = {
                "first_monitored": first["label"],
                "transition": first["transition"],
                "full_amplitude_first_time_ms": t,
                "first_stationary_rms_g": g,
                "scale": first["scale"],
                "remaining_pocket_normal_N": selected["pocket_normal_force_at_first_N"],
                "maximum_relative_change_across_controls": float(
                    max(abs(np.asarray(levels) / first["scale"] - 1))
                ),
                "layer_MPa": mt["metrics"]["layer_tension_MPa"]["maximum_MPa"],
                "layer_pct": mt["metrics"]["layer_tension_MPa"]["percent_of_coupon_mean"],
                "in_plane_pct": mt["metrics"]["in_plane_tension_MPa"]["percent_of_coupon_mean"],
            }
            for a, x in [(time, t), (level, g * 1000)]:
                a.plot(
                    x,
                    idx + offset,
                    marker=marker,
                    color=color,
                    ls="none",
                    ms=4.5,
                    label=title if idx == 0 else None,
                )
                txt = f"{x:.2g}" if x < 1 else f"{x:.3g}"
                a.annotate(
                    txt,
                    (x, idx + offset),
                    xytext=(5, 0),
                    textcoords="offset points",
                    va="center",
                    fontsize=8,
                    color=color,
                )
    for a in (time, level):
        a.set_yticks([0, 1, 2], ["Base Z", "Base Y", "Base X"])
        a.set_ylim(-0.5, 2.5)
        a.grid(axis="x", color="#dddddd", lw=0.5)
        a.spines[["top", "right", "left"]].set_visible(False)
        a.tick_params(axis="y", length=0)
    time.set_xlim(0, 12)
    time.set_xlabel("Time from start [ms]")
    time.set_title(
        r"First switch at the reference input (14.14 $g$ RMS)", fontsize=10, loc="left", color="#08357E"
    )
    level.set_xscale("log")
    level.set_xlim(0.20, 41)
    level.set_xticks([0.3, 1, 3, 10, 30], ["0.3", "1", "3", "10", "30"])
    level.set_xlabel(r"Stationary input level [$10^{-3}\,g$ RMS]")
    level.set_title("Lowest switch level over nine seconds", fontsize=10, loc="left", color="#08357E")
    fig.legend(*time.get_legend_handles_labels(), loc="outside lower center", ncols=3, frameon=False, fontsize=9)
    fig.savefig(ROOT / "docs/figures/snug-vibration-level.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)
    first = min((r["axes"]["Z"]["scale"], branch) for branch, r in results.items())
    shared_load = []
    hashes = set()
    for b in ("bare", *names):
        method = "exact" if b.endswith("_mesh15") else "native"
        f = AUDIT / f"{b}_Z_bond_{method}.json"
        known = read(f)
        assert known["axis"] == "Z" and known["variant"] == b and known["samples"] == 9 * FS + 1
        hashes.add(known["load_sha256"])
        if b != "bare":
            s = read(AUDIT / f"{b}_vibration_level.json")
            assert s["modal_rst_sha256"] == known["basis_rst_sha256"]
            assert s["axes"]["Z"]["input_sha256"] == known["load_sha256"]
        shared_load.append(
            {
                "branch": b,
                "source_sha256": digest(f),
                "peak_dynamic_bond_mN": 1000 * first[0] * known["largest_bond"]["magnitude_N"],
            }
        )
    assert len(hashes) == 1
    write_json(
        AUDIT / "seeded_vibration_level_comparison.json",
        {
            "models": results,
            "base_Z_reference": {
                "governing_branch": first[1],
                "scale": first[0],
                "input_sha256": hashes.pop(),
                "stationary_rms_g": results[first[1]]["axes"]["Z"]["first_stationary_rms_g"],
                "maximum_bond_force_increment": shared_load,
            },
        },
    )


if __name__ == "__main__":
    draw()

#!/usr/bin/env python3
"""Freeze accepted MAPDL data read-only, or rebuild bilingual figures offline.

Capture: python make_results_figures.py --capture ../../ansystmp/windows
Rebuild: python make_results_figures.py
Only docs/analysis is written; no solver commands are executed.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from latex_style import configure_latex, plot_samples

configure_latex()

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "accepted_results_snapshot.json"
THICKNESS = 4.7625  # mm, initial phenolic thickness
THRESHOLD = .98
WINDOW = .6625  # s, fixed recent fitting window


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def front(means, threshold=THRESHOLD):
    """Contiguous front from original bore, interpolated between row centres."""
    pitch = THICKNESS / len(means)
    j = next((i for i, a in enumerate(means) if a < threshold), len(means))
    if j == 0:
        return 0.0
    if j == len(means):
        return THICKNESS
    return (j - .5 + (means[j - 1] - threshold) /
            (means[j - 1] - means[j])) * pitch


def fit(points, end):
    selected = [p for p in points if end - WINDOW - 1e-9 <= p["time_s"] <= end + 1e-9]
    if len(selected) < 3:
        raise ValueError("At least three accepted samples required")
    ts = [p["time_s"] for p in selected]
    xs = [p["front_98_mm"] for p in selected]
    tm, xm = sum(ts) / len(ts), sum(xs) / len(xs)
    speed = sum((t-tm)*(x-xm) for t,x in zip(ts,xs)) / sum((t-tm)**2 for t in ts)
    intercept = xm - speed*tm
    assert speed > 0
    return {"sample_count": len(ts), "start_s": ts[0], "end_s": ts[-1],
            "speed_mm_s": speed, "intercept_mm": intercept,
            "targets_s": [(THICKNESS*q-intercept)/speed for q in (.25,.5,.75)]}


def capture(runtime):
    raw = (runtime / "state.json").read_bytes()
    state = json.loads(raw)
    index = state["index"]
    mesh_raw = (runtime / "mesh_map.json").read_bytes()
    mesh = json.loads(mesh_raw)
    rows = [[(str(f["element"]), f["volume"]) for f in row] for row in mesh["rows"]]
    assert len(rows) == 240 and all(len(row) == 500 for row in rows)
    sources = {"state.json": digest(raw), "mesh_map.json": digest(mesh_raw)}
    audits = []
    for path in sorted((runtime / "checkpoints").glob("audit_*.json")):
        idx = int(path.stem.split("_")[1])
        if idx > index:
            continue
        data = path.read_bytes()
        audit = json.loads(data)
        assert audit["time_s"] <= state["time_s"] + 1e-9
        assert abs(audit["energy_relative_error"]) <= .05
        assert abs(audit["hot_power_relative_error"]) <= .02
        audit["index"] = idx
        audits.append(audit)
        sources[str(path.relative_to(runtime))] = digest(data)
    assert audits[-1]["index"] == index
    assert all(b["time_s"] > a["time_s"] for a,b in zip(audits,audits[1:]))
    points = []
    profiles = []
    selected_profiles = {min(160,index), min(240,index), min(320,index), index}
    for path in sorted((runtime / "checkpoints").glob("state_*.json.gz")):
        idx = int(path.name.split("_")[1].split(".")[0])
        if idx > index or (idx % 4 and idx not in {358,index}):
            continue
        data = path.read_bytes()
        s = json.loads(gzip.decompress(data))
        assert s["index"] == idx
        alpha = s["alpha"]
        means = [sum(alpha[e]*v for e,v in row)/sum(v for e,v in row) for row in rows]
        assert all(math.isfinite(a) and 0 <= a <= 1.000001 for a in means)
        points.append({"index": idx, "time_s": s["time_s"],
                       "front_98_mm": front(means),
                       "front_90_mm": front(means,.90), "front_99_mm": front(means,.99)})
        if idx in selected_profiles:
            profiles.append({"index": idx, "time_s": s["time_s"], "alpha_row_mean": means})
        sources[str(path.relative_to(runtime))] = digest(data)
    assert points[-1]["index"] == index
    assert abs(points[-1]["time_s"]-state["time_s"]) < 1e-9
    snapshot = {"captured_utc": datetime.now(timezone.utc).isoformat(),
                "accepted_index": index, "accepted_time_s": state["time_s"],
                "status_at_capture": state["status"],
                "source_runtime": "v0/ansystmp/windows", "source_sha256": sources,
                "definition": "Contiguous alpha >= 0.98 front from original bore; volume-weighted radial-row means; linear interpolation between centres. Deleted rows retain their accepted alpha. Not material removal.",
                "fit_window_s": WINDOW, "sample_stride": 4,
                "audits": audits, "fronts": points, "profiles": profiles}
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2, allow_nan=False)+"\n")
    return snapshot


def save(fig, name, lang):
    if lang == "fr":
        # Same decimal-comma convention as the earlier French report figures.
        for ax in fig.axes:
            formatter = lambda value, _: format(value, "g").replace(".", "{,}")
            ax.xaxis.set_major_formatter(FuncFormatter(formatter))
            ax.yaxis.set_major_formatter(FuncFormatter(formatter))
    fig.savefig(ROOT / f"{name}_{lang}.pdf", bbox_inches="tight")
    fig.savefig(ROOT / f"{name}_{lang}.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def plots(s, lang):
    fr = lang == "fr"
    def tr(a,b):
        return ((a if fr else b).replace("%", r"\%")
                .replace("α", r"$\alpha$").replace("≠", r"$\ne$"))
    def number(value, decimals=4):
        text = f"{value:.{decimals}f}"
        return text.replace(".", ",") if fr else text
    audits, points = s["audits"], s["fronts"]
    ts = [a["time_s"] for a in audits]
    ft = [p["time_s"] for p in points]
    title = tr("Résultats acceptés", "Accepted results") + f" | t = {number(s['accepted_time_s'])} s | index {s['accepted_index']}"
    xlabel = tr("Temps physique depuis l'allumage [s]", "Physical time since ignition [s]")
    fig, axs = plt.subplots(2,2,figsize=(10,7.2), layout="constrained")
    ax=axs[0,0]
    plot_samples(ax,ts,[a["Ts_mean_C"] for a in audits],color="#08357E")
    ax.set(title=tr("Température moyenne de la face chaude", "Mean hot-face temperature"),ylabel=r"$^\circ\mathrm{C}$")
    ax=axs[0,1]
    plot_samples(ax,ft,[p["front_98_mm"] for p in points],label=tr("Front de pyrolyse α = 0,98", "Pyrolysis front α = 0.98"))
    plot_samples(ax,ts,[a["phenolic_removed_thickness_m"]*1000 for a in audits],drawstyle="steps-post",label=tr("Épaisseur supprimée", "Removed thickness"),color="#A04A00")
    ax.annotate(tr("Dernier état : ", "Latest state: ")+number(points[-1]["front_98_mm"],3)+" mm",
                (ft[-1],points[-1]["front_98_mm"]),xytext=(-90,-16),
                textcoords="offset points",ha="right",fontsize=8.2,
                arrowprops={"arrowstyle":"-","color":"#6B3100","linewidth":.6})
    ax.set(title=tr("Transformation et suppression distinctes", "Transformation is not removal"),ylabel="mm")
    ax.legend(fontsize=8)
    ax=axs[1,0]
    for key,label in [("gas_cumulative_full_ring_kg",tr("Gaz de pyrolyse", "Pyrolysis gas")),("char_cumulative_full_ring_kg",tr("Carbone consommé", "Consumed carbon"))]:
        plot_samples(ax,ts,[a[key]*1000 for a in audits],label=label)
    ax.set(title=tr("Masses cumulées : anneau complet, L = 50 mm", "Cumulative masses: full ring, L = 50 mm"),ylabel="g")
    ax.legend(fontsize=8)
    ax=axs[1,1]
    plot_samples(ax,ts,[100*a["energy_relative_error"] for a in audits],label=tr("Erreur énergétique", "Energy error"))
    plot_samples(ax,ts,[100*a["hot_power_relative_error"] for a in audits],label=tr("Erreur convection chaude", "Hot convection error"))
    ax.axhline(5,color="#A04A00",ls="--",label=tr("Seuil énergie 5 %", "Energy limit 5%"))
    ax.axhline(2,color="#777777",ls=":",label=tr("Seuil convection 2 %", "Convection limit 2%"))
    ax.set(title=tr("Bilans des pas acceptés", "Accepted-step balance checks"),ylabel=r"\%")
    ax.legend(fontsize=8,ncol=2)
    kill = next((a["time_s"] for a in audits if a["rows_removed"]),None)
    for ax in axs.flat:
        ax.set_xlabel(xlabel)
        if kill is not None:ax.axvline(kill,color="#A64D79",ls=":",lw=1.1)
    fig.suptitle(title+"\n"+tr("Pointillé vertical : première suppression de rangée", "Vertical dotted line: first row removal"),fontsize=12)
    save(fig,"newmotor_results",lang)

    fig,axs=plt.subplots(1,2,figsize=(10,4.3),layout="constrained")
    depth=[(i+.5)*THICKNESS/240 for i in range(240)]
    for profile in s["profiles"]:
        plot_samples(axs[0],depth,profile["alpha_row_mean"],highlight_latest=False,label=f"{number(profile['time_s'])} s")
    axs[0].axhline(.98,ls="--",color="#777777",label=tr("α = 0,98", "α = 0.98"))
    axs[0].set(xlim=(0,1.3),ylim=(0,1.04),xlabel=tr("Profondeur depuis l'alésage initial [mm]", "Depth from original bore [mm]"),ylabel=tr("Conversion moyenne par rangée α", "Row-mean conversion α"),title=tr("Profils radiaux de conversion", "Radial conversion profiles"))
    axs[0].legend(fontsize=8)
    for threshold in (90,98,99):
        value = number(threshold/100,2).replace(",", "{,}")
        plot_samples(axs[1],ft,[p[f"front_{threshold}_mm"] for p in points],label=rf"$\alpha = {value}$")
    axs[1].set(xlabel=xlabel,ylabel=tr("Profondeur du front [mm]", "Front depth [mm]"),title=tr("Front continu depuis la face chaude", "Contiguous front from hot face"))
    axs[1].legend()
    fig.suptitle(title,fontsize=12)
    save(fig,"newmotor_conversion",lang)

    regular=[p for p in points if p["index"]%4==0 or p["index"]==s["accepted_index"]]
    current=fit(regular,s["accepted_time_s"])
    previous=fit([p for p in points if p["index"]%4==0 or p["index"]==358],4.6625)
    evolution=[(p["time_s"],fit(regular,p["time_s"])) for p in regular if p["time_s"]>=3.5]
    fig,axs=plt.subplots(1,2,figsize=(10,4.6),layout="constrained")
    ax=axs[0]
    plot_samples(ax,ft,[100*p["front_98_mm"]/THICKNESS for p in points],color="#08357E",label=tr("Calcul accepté", "Accepted calculation"))
    horizon=max(current["targets_s"][-1],previous["targets_s"][-1])+1
    for result,color,label in [(previous,"#999999",tr("Projection précédente", "Previous projection")),(current,"#A04A00",tr("Projection actualisée", "Updated projection"))]:
        xx=[result["end_s"],horizon]
        ax.plot(xx,[100*(result["speed_mm_s"]*t+result["intercept_mm"])/THICKNESS for t in xx],ls="--",color=color,label=label)
    for q,t in zip((25,50,75),current["targets_s"]):
        ax.axhline(q,color="#dddddd",lw=.8)
        ax.scatter([t],[q],marker="o",facecolors="white",edgecolors="#A04A00",s=31,zorder=3)
        ax.annotate(f"{number(t,1)} s",(t,q),xytext=(-5,5) if q == 75 else (5,5),
                    ha="right" if q == 75 else "left",textcoords="offset points",fontsize=8)
    ax.axvspan(s["accepted_time_s"],horizon,color="#eeeeee",alpha=.45)
    ax.axvline(7,color="#777777",ls=":",label=tr("Horizon du calcul : 7 s", "Simulation horizon: 7 s"))
    ax.set(xlim=(0,horizon),ylim=(0,85),xlabel=xlabel,ylabel=tr("Épaisseur initiale pyrolysée [%]", "Pyrolysed initial thickness [%]"),title=tr("Au-delà du calcul : extrapolation linéaire", "Beyond the calculation: linear extrapolation"))
    ax.legend(fontsize=7.5,loc="upper left")
    ax=axs[1]
    for i,q in enumerate((25,50,75)):
        plot_samples(ax,[t for t,r in evolution],[r["targets_s"][i] for t,r in evolution],label=rf"{q}\,\%")
    ax.set(xlabel=tr("Dernier temps accepté utilisé [s]", "Last accepted time used [s]"),ylabel=tr("Temps prédit depuis l'allumage [s]", "Predicted time since ignition [s]"),title=tr("Stabilité de la projection (fenêtre 0,6625 s)", "Projection stability (0.6625 s window)"))
    ax.legend()
    fig.suptitle(tr("Exploratoire, non calibré : pyrolyse ≠ disparition de matière", "Exploratory, uncalibrated: pyrolysis ≠ material disappearance"),fontsize=12)
    save(fig,"newmotor_projections",lang)
    return current,previous


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture",type=Path)
    args=parser.parse_args()
    s=capture(args.capture.resolve()) if args.capture else json.loads(SNAPSHOT.read_text())
    for lang in ("fr","en"):
        current,previous=plots(s,lang)
    print(json.dumps({"index":s["accepted_index"],"time_s":s["accepted_time_s"],
                      "latest_front":s["fronts"][-1],"fit":current,"previous_fit":previous,
                      "latest_audit":s["audits"][-1]},indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create bilingual figures for the completed 0.10-degree sector simulation.

Only complete rows from the read-only history snapshot are used.  The rate is
the finite difference of the controller's cumulative virtual recession; it is
therefore a temporal, step-averaged quantity and not a DPF spatial statistic.
"""

from pathlib import Path
import os
import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402


ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "simulation3_sector_history_snapshot.csv"
ONSET_UM = 1.0

TEXT = {
    "fr": {
        "time": r"Temps physique, $t$ [$\mathrm{s}$]",
        "alpha": r"Conversion moyenne, $\overline{\alpha}$",
        "rec": r"Récession virtuelle cumulée [$\mu\mathrm{m}$]",
        "rate": r"Vitesse de récession par macro-pas [$\mu\mathrm{m}\,\mathrm{s}^{-1}$]",
        "rec_t": "Récession virtuelle du secteur fin en fonction du temps",
        "rate_t": "Vitesse de récession du secteur fin en fonction du temps",
        "rec_a": "Récession virtuelle en fonction de la conversion moyenne",
        "rate_a": "Vitesse de récession en fonction de la conversion moyenne",
        "onset": r"Premier état avec $s\geq1\,\mu\mathrm{m}$",
        "deactivation": "Désactivation de rangée",
        "latest": r"Dernier état convergé : $t={t}\,\mathrm{{s}}$, $s={s}\,\mu\mathrm{{m}}$",
        "mean": r"$\overline{\alpha}$",
        "minimum": r"$\alpha_{\min}$",
        "conversion_title": "Conversion de la première couche phénolique",
        "conversion_y": "Conversion locale de la couche active",
        "flux": r"Flux gazeux [$\mathrm{kg}\,\mathrm{m}^{-2}\,\mathrm{s}^{-1}$]",
        "flow": r"Débit du secteur [$\mathrm{mg}\,\mathrm{s}^{-1}$]",
        "h": r"Coefficient convectif effectif [$\mathrm{W}\,\mathrm{m}^{-2}\,\mathrm{K}^{-1}$]",
        "temp": r"Température maximale [$^\circ\mathrm{C}$]",
        "gas_title": "Dégazage, soufflage et température de surface",
        "history_note": "Différence finie de l'historique convergé du contrôleur",
    },
    "en": {
        "time": r"Physical time, $t$ [$\mathrm{s}$]",
        "alpha": r"Mean conversion, $\overline{\alpha}$",
        "rec": r"Accumulated virtual recession [$\mu\mathrm{m}$]",
        "rate": r"Macro-step recession rate [$\mu\mathrm{m}\,\mathrm{s}^{-1}$]",
        "rec_t": "Thin-sector virtual recession versus time",
        "rate_t": "Thin-sector recession rate versus time",
        "rec_a": "Virtual recession versus mean conversion",
        "rate_a": "Recession rate versus mean conversion",
        "onset": r"First state with $s\geq1\,\mu\mathrm{m}$",
        "deactivation": "Radial-row deactivation",
        "latest": r"Latest converged state: $t={t}\,\mathrm{{s}}$, $s={s}\,\mu\mathrm{{m}}$",
        "mean": r"$\overline{\alpha}$",
        "minimum": r"$\alpha_{\min}$",
        "conversion_title": "Conversion of the first phenolic layer",
        "conversion_y": "Local conversion of the active layer",
        "flux": r"Gas mass flux [$\mathrm{kg}\,\mathrm{m}^{-2}\,\mathrm{s}^{-1}$]",
        "flow": r"Sector flow rate [$\mathrm{mg}\,\mathrm{s}^{-1}$]",
        "h": r"Effective convection coefficient [$\mathrm{W}\,\mathrm{m}^{-2}\,\mathrm{K}^{-1}$]",
        "temp": r"Maximum temperature [$^\circ\mathrm{C}$]",
        "gas_title": "Outgassing, blowing, and surface temperature",
        "history_note": "Finite difference of the converged controller history",
    },
    "de": {
        "time": r"Physikalische Zeit, $t$ [$\mathrm{s}$]",
        "alpha": r"Mittlerer Umsatz, $\overline{\alpha}$",
        "rec": r"Kumulierte virtuelle Rezession [$\mu\mathrm{m}$]",
        "rate": r"Rezessionsgeschwindigkeit je Makroschritt [$\mu\mathrm{m}\,\mathrm{s}^{-1}$]",
        "rec_t": "Virtuelle Rezession des Dünnsektors über der Zeit",
        "rate_t": "Rezessionsgeschwindigkeit des Dünnsektors über der Zeit",
        "rec_a": "Virtuelle Rezession über dem mittleren Umsatz",
        "rate_a": "Rezessionsgeschwindigkeit über dem mittleren Umsatz",
        "onset": r"Erster Zustand mit $s\geq1\,\mu\mathrm{m}$",
        "deactivation": "Deaktivierung einer Radialreihe",
        "latest": r"Letzter konvergierter Zustand: $t={t}\,\mathrm{{s}}$, $s={s}\,\mu\mathrm{{m}}$",
        "mean": r"$\overline{\alpha}$",
        "minimum": r"$\alpha_{\min}$",
        "conversion_title": "Umsatz der ersten Phenolharzschicht",
        "conversion_y": "Lokaler Umsatz der aktiven Schicht",
        "flux": r"Gasmassenflussdichte [$\mathrm{kg}\,\mathrm{m}^{-2}\,\mathrm{s}^{-1}$]",
        "flow": r"Massenstrom des Sektors [$\mathrm{mg}\,\mathrm{s}^{-1}$]",
        "h": r"Effektiver Konvektionskoeffizient [$\mathrm{W}\,\mathrm{m}^{-2}\,\mathrm{K}^{-1}$]",
        "temp": r"Maximaltemperatur [$^\circ\mathrm{C}$]",
        "gas_title": "Ausgasung, Blowing und Oberflächentemperatur",
        "history_note": "Finite Differenz der konvergierten Reglerhistorie",
    },
}


def setup_style():
    os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="mpl_sim3_sector_"))
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9.2,
            "text.usetex": True,
            "text.latex.preamble": r"\usepackage[T1]{fontenc}\usepackage[utf8]{inputenc}\usepackage{lmodern}",
            "axes.grid": True,
            "grid.alpha": 0.24,
            "grid.linewidth": 0.5,
            "axes.axisbelow": True,
            "pdf.fonttype": 42,
        }
    )


def load_history():
    # The controller writes narrow integer fields for ``layer`` and
    # ``killed_for_next_step``.  Once 200 elements are killed, those fields
    # become ``****``/``**``.  They are intentionally excluded here; all
    # plotted physical quantities remain valid floating-point columns.
    names = (
        "time_s", "hot_radius_m", "alpha_avg", "alpha_min", "gas_kg_s",
        "gas_kg_m2_s", "h_W_m2_K", "Ts_max_C", "recession_m",
    )
    data = np.genfromtxt(
        HISTORY,
        names=names,
        dtype=float,
        encoding="utf-8",
        skip_header=1,
        usecols=(0, 2, 3, 4, 5, 6, 7, 8, 9),
    )
    data = np.atleast_1d(data)
    required = (
        "time_s", "alpha_avg", "alpha_min", "gas_kg_s",
        "gas_kg_m2_s", "h_W_m2_K", "Ts_max_C", "recession_m",
    )
    if any(name not in data.dtype.names for name in required):
        raise RuntimeError("Incomplete or incompatible history snapshot")
    valid = np.ones(data.size, dtype=bool)
    for name in required:
        valid &= np.isfinite(np.asarray(data[name], dtype=float))
    data = data[valid]
    data = data[np.argsort(data["time_s"])]
    if data.size < 2 or np.any(np.diff(data["time_s"]) <= 0):
        raise RuntimeError("History snapshot is empty or non-monotonic")
    return data


def local(value, decimals, lang):
    answer = f"{value:.{decimals}f}"
    return answer.replace(".", ",") if lang in ("fr", "de") else answer


def formatter(lang, decimals=1):
    return FuncFormatter(lambda value, _pos: local(value, decimals, lang))


def finish(fig, output):
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def add_onset(ax, onset_t, text, annotate=True):
    ax.axvline(onset_t, color="#38761D", linestyle="--", linewidth=1.0, zorder=1)
    if annotate:
        ax.text(
            onset_t, 0.98, text, transform=ax.get_xaxis_transform(), rotation=90,
            ha="right", va="top", color="#285214", fontsize=7.7,
        )


def deactivation_times(data):
    changed = np.flatnonzero(np.diff(data["hot_radius_m"]) > 1.0e-9)
    return np.asarray(data["time_s"][changed], dtype=float)


def add_deactivations(ax, event_times, text, annotate=True):
    for index, event_t in enumerate(event_times):
        ax.axvline(event_t, color="#A64D79", linestyle=":", linewidth=1.1, zorder=1)
        if annotate:
            ax.text(
                event_t, 0.98, text if index == 0 else f"{event_t:.2f} s",
                transform=ax.get_xaxis_transform(), rotation=90,
                ha="right", va="top", color="#743454", fontsize=7.7,
            )


def plot_recession(data, lang, x_kind):
    text = TEXT[lang]
    t = data["time_s"]
    alpha = data["alpha_avg"]
    recession = data["recession_m"] * 1.0e6
    onset_t = t[np.flatnonzero(recession >= ONSET_UM)[0]]
    event_times = deactivation_times(data)
    x = t if x_kind == "time" else alpha
    fig, ax = plt.subplots(figsize=(7.25, 4.25))
    ax.plot(x, recession, color="#08357E", marker="o", markersize=2.8, linewidth=1.55)
    ax.scatter([x[-1]], [recession[-1]], color="#A04A00", s=31, zorder=3)
    ax.set_xlabel(text[x_kind])
    ax.set_ylabel(text["rec"])
    ax.set_title(text["rec_t" if x_kind == "time" else "rec_a"], pad=8)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.xaxis.set_major_formatter(formatter(lang, 1 if x_kind == "time" else 2))
    ax.yaxis.set_major_formatter(formatter(lang, 0))
    if x_kind == "time":
        add_onset(ax, onset_t, text["onset"])
        add_deactivations(ax, event_times, text["deactivation"])
    annotation = text["latest"].format(t=local(t[-1], 2, lang), s=local(recession[-1], 1, lang))
    ax.annotate(annotation, (x[-1], recession[-1]), xytext=(-8, 14),
                textcoords="offset points", ha="right", fontsize=8.2,
                arrowprops={"arrowstyle": "-", "color": "#6B3100", "linewidth": 0.6})
    suffix = "time" if x_kind == "time" else "alpha_avg"
    finish(fig, ROOT / f"simulation3_sector_recession_vs_{suffix}_{lang}.pdf")


def plot_rate(data, lang, x_kind):
    text = TEXT[lang]
    t = data["time_s"]
    alpha = data["alpha_avg"]
    recession = data["recession_m"] * 1.0e6
    t0 = np.r_[0.0, t]
    s0 = np.r_[0.0, recession]
    rate = np.diff(s0) / np.diff(t0)
    onset_t = t[np.flatnonzero(recession >= ONSET_UM)[0]]
    event_times = deactivation_times(data)
    x = t if x_kind == "time" else alpha
    fig, ax = plt.subplots(figsize=(7.25, 4.25))
    ax.step(x, rate, where="mid", color="#A04A00", linewidth=1.45)
    ax.plot(x, rate, linestyle="none", marker="o", markersize=2.5, color="#A04A00")
    ax.set_xlabel(text[x_kind])
    ax.set_ylabel(text["rate"])
    ax.set_title(text["rate_t" if x_kind == "time" else "rate_a"], pad=8)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.xaxis.set_major_formatter(formatter(lang, 1 if x_kind == "time" else 2))
    ax.yaxis.set_major_formatter(formatter(lang, 0))
    if x_kind == "time":
        add_onset(ax, onset_t, text["onset"])
        add_deactivations(ax, event_times, text["deactivation"])
    ax.text(0.99, 0.03, text["history_note"], transform=ax.transAxes,
            ha="right", va="bottom", fontsize=7.5, color="#555555")
    suffix = "time" if x_kind == "time" else "alpha_avg"
    finish(fig, ROOT / f"simulation3_sector_recession_rate_vs_{suffix}_{lang}.pdf")


def plot_conversion(data, lang):
    text = TEXT[lang]
    t = data["time_s"]
    recession = data["recession_m"] * 1.0e6
    onset_t = t[np.flatnonzero(recession >= ONSET_UM)[0]]
    event_times = deactivation_times(data)
    fig, ax = plt.subplots(figsize=(7.25, 4.25))
    ax.plot(t, data["alpha_avg"], color="#08357E", linewidth=1.65, label=text["mean"])
    ax.plot(t, data["alpha_min"], color="#FF7F0E", linewidth=1.15,
            linestyle="--", label=text["minimum"])
    add_onset(ax, onset_t, text["onset"])
    add_deactivations(ax, event_times, text["deactivation"])
    ax.set_xlabel(text["time"])
    ax.set_ylabel(text["conversion_y"])
    ax.set_title(text["conversion_title"], pad=8)
    ax.set_xlim(left=0)
    ax.set_ylim(0, 1.03)
    ax.xaxis.set_major_formatter(formatter(lang, 1))
    ax.yaxis.set_major_formatter(formatter(lang, 1))
    ax.legend(loc="lower right")
    finish(fig, ROOT / f"simulation3_sector_conversion_vs_time_{lang}.pdf")


def plot_thermal_gas(data, lang):
    text = TEXT[lang]
    t = data["time_s"]
    event_times = deactivation_times(data)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.25, 6.35), sharex=True)
    p1 = ax1.plot(t, data["gas_kg_m2_s"], color="#08357E", linewidth=1.55,
                  label=text["flux"])[0]
    ax1.set_ylabel(text["flux"], color="#08357E")
    ax1.tick_params(axis="y", colors="#08357E")
    ax1b = ax1.twinx()
    p2 = ax1b.plot(t, data["gas_kg_s"] * 1.0e6, color="#A64D79", linewidth=1.35,
                   label=text["flow"])[0]
    ax1b.set_ylabel(text["flow"], color="#A64D79")
    ax1b.tick_params(axis="y", colors="#A64D79")
    ax1.legend([p1, p2], [p1.get_label(), p2.get_label()], loc="lower right")

    p3 = ax2.plot(t, data["h_W_m2_K"], color="#38761D", linewidth=1.55,
                  label=text["h"])[0]
    ax2.set_ylabel(text["h"], color="#38761D")
    ax2.tick_params(axis="y", colors="#38761D")
    ax2b = ax2.twinx()
    p4 = ax2b.plot(t, data["Ts_max_C"], color="#A04A00", linewidth=1.45,
                   label=text["temp"])[0]
    ax2b.set_ylabel(text["temp"], color="#A04A00")
    ax2b.tick_params(axis="y", colors="#A04A00")
    ax2.legend([p3, p4], [p3.get_label(), p4.get_label()], loc="center right")
    ax2.set_xlabel(text["time"])
    add_deactivations(ax1, event_times, text["deactivation"])
    add_deactivations(ax2, event_times, text["deactivation"], annotate=False)
    ax2.xaxis.set_major_formatter(formatter(lang, 1))
    ax1.set_title(text["gas_title"], pad=9)
    finish(fig, ROOT / f"simulation3_sector_thermal_gas_overview_{lang}.pdf")


def main():
    setup_style()
    data = load_history()
    for lang in ("fr", "en", "de"):
        for x_kind in ("time", "alpha"):
            plot_recession(data, lang, x_kind)
            plot_rate(data, lang, x_kind)
        plot_conversion(data, lang)
        plot_thermal_gas(data, lang)
    print(f"Generated 18 figures from {data.size} converged states through t={data['time_s'][-1]:.2f} s")


if __name__ == "__main__":
    main()

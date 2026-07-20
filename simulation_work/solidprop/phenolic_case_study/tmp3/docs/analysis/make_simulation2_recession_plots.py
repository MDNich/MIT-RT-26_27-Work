#!/usr/bin/env python3
"""Plot the virtual recession recorded by ANSYS Simulation 2.

The script reads ``simulation2_history.csv`` without modifying it and creates
separate French and English vector PDFs for:

* virtual recession versus physical time;
* virtual recession versus mean conversion ``alpha_avg``.
* mean recession rate per converged time step versus physical time;
* mean recession rate per converged time step versus mean conversion.

Re-running the script updates the figures with every fully synchronized row
currently available in the history file.
"""

import argparse
import os
import tempfile
from pathlib import Path

import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402


ROOT = Path(__file__).resolve().parent
DEFAULT_HISTORY = (
    ROOT.parents[2]
    / "tmp3_sim2"
    / "resume_runs"
    / "ScrResume_step16_v2_20260719"
    / "simulation2_history.csv"
)
DEFAULT_RATE_STATS = ROOT / "simulation2_surface_recession_rate_stats.csv"

TEXT = {
    "fr": {
        "time_xlabel": r"Temps physique, $t$ [$\mathrm{s}$]",
        "alpha_xlabel": r"Conversion moyenne du phénolique, $\overline{\alpha}$",
        "ylabel": r"Récession virtuelle cumulée [$\mu\mathrm{m}$]",
        "time_title": r"Récession virtuelle en fonction du temps",
        "alpha_title": r"Récession virtuelle en fonction de la conversion moyenne",
        "rate_ylabel": r"Vitesse moyenne de récession, "
        r"$\langle\dot{s}\rangle$ "
        r"[$\mu\mathrm{m}\,\mathrm{s}^{-1}$]",
        "rate_time_title": r"Vitesse de récession en fonction du temps",
        "rate_alpha_title": (
            r"Vitesse de récession en fonction de la conversion moyenne"
        ),
        "latest": r"Dernier état : $t={time}\,\mathrm{{s}}$, "
        r"$\overline{{\alpha}}={alpha}$, $s={recession}\,\mu\mathrm{{m}}$",
        "latest_rate": r"Dernier intervalle : $t={time}\,\mathrm{{s}}$, "
        r"$\overline{{\alpha}}={alpha}$, "
        r"$\langle\dot{{s}}\rangle={rate}\pm{std}\,"
        r"\mu\mathrm{{m}}\,\mathrm{{s}}^{{-1}}$",
        "rate_population": r"Barres : $\pm1\sigma$ spatial sur "
        r"$N={count}$ nœuds de la face intérieure",
    },
    "en": {
        "time_xlabel": r"Physical time, $t$ [$\mathrm{s}$]",
        "alpha_xlabel": r"Mean phenolic conversion, $\overline{\alpha}$",
        "ylabel": r"Cumulative virtual recession [$\mu\mathrm{m}$]",
        "time_title": r"Virtual recession versus time",
        "alpha_title": r"Virtual recession versus mean conversion",
        "rate_ylabel": r"Mean recession rate, $\langle\dot{s}\rangle$ "
        r"[$\mu\mathrm{m}\,\mathrm{s}^{-1}$]",
        "rate_time_title": r"Recession rate versus time",
        "rate_alpha_title": r"Recession rate versus mean conversion",
        "latest": r"Latest state: $t={time}\,\mathrm{{s}}$, "
        r"$\overline{{\alpha}}={alpha}$, $s={recession}\,\mu\mathrm{{m}}$",
        "latest_rate": r"Latest interval: $t={time}\,\mathrm{{s}}$, "
        r"$\overline{{\alpha}}={alpha}$, "
        r"$\langle\dot{{s}}\rangle={rate}\pm{std}\,"
        r"\mu\mathrm{{m}}\,\mathrm{{s}}^{{-1}}$",
        "rate_population": r"Bars: spatial $\pm1\sigma$ over "
        r"$N={count}$ inner-surface nodes",
    },
}


def configure_matplotlib():
    """Apply the LaTeX-based report style."""
    mpl_tmp = Path(tempfile.mkdtemp(prefix="mpl_sim2_recession_"))
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_tmp))
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9.5,
            "text.usetex": True,
            "text.latex.preamble": (
                r"\usepackage[T1]{fontenc}"
                r"\usepackage[utf8]{inputenc}"
                r"\usepackage{lmodern}"
            ),
            "axes.edgecolor": "#333333",
            "axes.labelcolor": "#111111",
            "xtick.color": "#111111",
            "ytick.color": "#111111",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.24,
            "grid.color": "#7f7f7f",
            "grid.linewidth": 0.5,
            "axes.axisbelow": True,
            "pdf.fonttype": 42,
        }
    )


def load_history(path):
    """Return valid, time-sorted rows from the whitespace-delimited history."""
    data = np.genfromtxt(path, names=True, dtype=float, encoding="utf-8")
    data = np.atleast_1d(data)
    required = ("time_s", "alpha_avg", "recession_m")
    if any(name not in data.dtype.names for name in required):
        raise RuntimeError("History file does not contain the expected columns.")

    time_s = np.asarray(data["time_s"], dtype=float)
    alpha_avg = np.asarray(data["alpha_avg"], dtype=float)
    recession_um = 1.0e6 * np.asarray(data["recession_m"], dtype=float)
    valid = (
        np.isfinite(time_s)
        & np.isfinite(alpha_avg)
        & np.isfinite(recession_um)
    )
    time_s = time_s[valid]
    alpha_avg = alpha_avg[valid]
    recession_um = recession_um[valid]
    if time_s.size == 0:
        raise RuntimeError("No complete history row was found.")

    order = np.argsort(time_s)
    return time_s[order], alpha_avg[order], recession_um[order]


def localized(value, decimals, language):
    """Format a number for a localized LaTeX annotation."""
    value_text = ("{:.%df}" % decimals).format(value)
    return value_text.replace(".", ",") if language == "fr" else value_text


def decimal_formatter(language, decimals=1):
    """Return a localized Matplotlib tick formatter."""
    def formatter(value, _position):
        return localized(value, decimals, language)

    return FuncFormatter(formatter)


def draw_plot(
    output,
    x,
    recession_um,
    time_s,
    alpha_avg,
    language,
    x_kind,
):
    """Create one localized vector PDF."""
    text = TEXT[language]
    fig, ax = plt.subplots(figsize=(7.25, 4.25))

    ax.plot(
        x,
        recession_um,
        color="#08357E",
        linewidth=1.55,
        marker="o",
        markersize=3.2,
        markerfacecolor="#9CBCE8",
        markeredgecolor="#08357E",
        markeredgewidth=0.55,
        zorder=3,
    )
    ax.scatter(
        [x[-1]],
        [recession_um[-1]],
        s=34,
        color="#A04A00",
        edgecolor="#6B3100",
        linewidth=0.6,
        zorder=4,
    )

    if x_kind == "time":
        ax.set_xlabel(text["time_xlabel"])
        ax.set_title(text["time_title"], pad=8)
        ax.xaxis.set_major_formatter(decimal_formatter(language, 1))
    else:
        ax.set_xlabel(text["alpha_xlabel"])
        ax.set_title(text["alpha_title"], pad=8)
        ax.xaxis.set_major_formatter(decimal_formatter(language, 2))

    ax.set_ylabel(text["ylabel"])
    ax.yaxis.set_major_formatter(decimal_formatter(language, 0))
    ax.set_xlim(left=0.0)
    ax.set_ylim(0.0, 1.16 * recession_um[-1])

    annotation = text["latest"].format(
        time=localized(time_s[-1], 2, language),
        alpha=localized(alpha_avg[-1], 3, language),
        recession=localized(recession_um[-1], 1, language),
    )
    ax.annotate(
        annotation,
        xy=(x[-1], recession_um[-1]),
        xytext=(-8, 14),
        textcoords="offset points",
        ha="right",
        va="bottom",
        fontsize=8.5,
        arrowprops={
            "arrowstyle": "-",
            "color": "#6B3100",
            "linewidth": 0.65,
        },
    )

    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def load_rate_statistics(path):
    """Read the DPF-derived full-surface rate distribution statistics."""
    data = np.genfromtxt(
        path,
        names=True,
        delimiter=",",
        dtype=None,
        encoding="utf-8",
    )
    data = np.atleast_1d(data)
    required = (
        "time_s",
        "alpha_avg",
        "surface_node_count",
        "recession_rate_mean_um_s",
        "recession_rate_std_um_s",
    )
    if any(name not in data.dtype.names for name in required):
        raise RuntimeError("Surface-rate CSV does not contain expected columns.")
    order = np.argsort(np.asarray(data["time_s"], dtype=float))
    return {
        "time_s": np.asarray(data["time_s"], dtype=float)[order],
        "alpha_avg": np.asarray(data["alpha_avg"], dtype=float)[order],
        "count": np.asarray(data["surface_node_count"], dtype=int)[order],
        "mean": np.asarray(
            data["recession_rate_mean_um_s"],
            dtype=float,
        )[order],
        "std": np.asarray(
            data["recession_rate_std_um_s"],
            dtype=float,
        )[order],
    }


def draw_rate_plot(
    output,
    x,
    rate_mean_um_s,
    rate_std_um_s,
    time_s,
    alpha_avg,
    surface_node_count,
    language,
    x_kind,
):
    """Create one localized full-surface mean and one-sigma rate PDF."""
    text = TEXT[language]
    fig, ax = plt.subplots(figsize=(7.25, 4.25))

    ax.fill_between(
        x,
        rate_mean_um_s - rate_std_um_s,
        rate_mean_um_s + rate_std_um_s,
        color="#9CBCE8",
        alpha=0.32,
        linewidth=0.0,
        zorder=2,
    )
    ax.errorbar(
        x,
        rate_mean_um_s,
        yerr=rate_std_um_s,
        fmt="-o",
        color="#08357E",
        linewidth=1.55,
        markersize=3.2,
        markerfacecolor="#9CBCE8",
        markeredgecolor="#08357E",
        markeredgewidth=0.55,
        ecolor="#315B91",
        elinewidth=0.75,
        capsize=2.0,
        capthick=0.75,
        zorder=3,
    )
    ax.scatter(
        [x[-1]],
        [rate_mean_um_s[-1]],
        s=34,
        color="#A04A00",
        edgecolor="#6B3100",
        linewidth=0.6,
        zorder=4,
    )

    if x_kind == "time":
        ax.set_xlabel(text["time_xlabel"])
        ax.set_title(text["rate_time_title"], pad=8)
        ax.xaxis.set_major_formatter(decimal_formatter(language, 1))
    else:
        ax.set_xlabel(text["alpha_xlabel"])
        ax.set_title(text["rate_alpha_title"], pad=8)
        ax.xaxis.set_major_formatter(decimal_formatter(language, 2))

    ax.set_ylabel(text["rate_ylabel"])
    ax.yaxis.set_major_formatter(decimal_formatter(language, 0))
    ax.set_xlim(left=0.0)
    ymin = min(
        0.0,
        0.92 * float(np.min(rate_mean_um_s - rate_std_um_s)),
    )
    ymax = 1.12 * float(np.max(rate_mean_um_s + rate_std_um_s))
    ax.set_ylim(ymin, ymax)

    annotation = text["latest_rate"].format(
        time=localized(time_s[-1], 2, language),
        alpha=localized(alpha_avg[-1], 3, language),
        rate=localized(rate_mean_um_s[-1], 2, language),
        std=localized(rate_std_um_s[-1], 3, language),
    )
    ax.annotate(
        annotation,
        xy=(x[-1], rate_mean_um_s[-1]),
        xytext=(-8, -28),
        textcoords="offset points",
        ha="right",
        va="top",
        fontsize=8.5,
        arrowprops={
            "arrowstyle": "-",
            "color": "#6B3100",
            "linewidth": 0.65,
        },
    )
    ax.text(
        0.02,
        0.97,
        text["rate_population"].format(
            count=int(surface_node_count[-1]),
        ),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
    )

    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history",
        type=Path,
        default=DEFAULT_HISTORY,
        help="Path to simulation2_history.csv.",
    )
    parser.add_argument(
        "--rate-stats",
        type=Path,
        default=DEFAULT_RATE_STATS,
        help="DPF-derived full-surface recession-rate statistics CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT,
        help="Directory for the generated vector PDFs.",
    )
    args = parser.parse_args()

    configure_matplotlib()
    time_s, alpha_avg, recession_um = load_history(args.history)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rate_stats = load_rate_statistics(args.rate_stats)
    if (
        rate_stats["time_s"].size != time_s.size
        or not np.allclose(rate_stats["time_s"], time_s, atol=1.0e-9)
    ):
        raise RuntimeError(
            "Surface-rate statistics and controller history are not synchronized."
        )

    for language in ("fr", "en"):
        draw_plot(
            args.output_dir
            / "simulation2_recession_vs_time_{}.pdf".format(language),
            time_s,
            recession_um,
            time_s,
            alpha_avg,
            language,
            "time",
        )
        draw_plot(
            args.output_dir
            / "simulation2_recession_vs_alpha_avg_{}.pdf".format(language),
            alpha_avg,
            recession_um,
            time_s,
            alpha_avg,
            language,
            "alpha",
        )
        draw_rate_plot(
            args.output_dir
            / "simulation2_recession_rate_vs_time_{}.pdf".format(language),
            rate_stats["time_s"],
            rate_stats["mean"],
            rate_stats["std"],
            rate_stats["time_s"],
            rate_stats["alpha_avg"],
            rate_stats["count"],
            language,
            "time",
        )
        draw_rate_plot(
            args.output_dir
            / "simulation2_recession_rate_vs_alpha_avg_{}.pdf".format(language),
            rate_stats["alpha_avg"],
            rate_stats["mean"],
            rate_stats["std"],
            rate_stats["time_s"],
            rate_stats["alpha_avg"],
            rate_stats["count"],
            language,
            "alpha",
        )

    print(
        "Generated eight PDFs from {} synchronized states through t={:.2f} s."
        .format(time_s.size, time_s[-1])
    )


if __name__ == "__main__":
    main()

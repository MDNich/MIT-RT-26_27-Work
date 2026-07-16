#!/usr/bin/env python3
"""Plot vertically stacked radial SVAR1 envelopes near each integer second.

The input CSV is produced by ``dpf_extract_svar1_time_profiles.py`` from the
distributed ANSYS ``file*.rth`` result partitions.  For every requested second,
the CSV contains the closest saved result set, the maximum globally averaged
elemental-nodal SVAR1 value in each one-percent radial band of ``phe0``, and the
0.80, 0.90, and 0.95 isoconversion depths.

The script produces separate French and English vector PDFs.  It does not
modify the existing last-converged-state figure.
"""

import argparse
import csv
import math
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402


ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "svar1_time_profiles_1pct.csv"
DEFAULT_PDF_FR = ROOT / "svar1_time_profiles_1pct_fr.pdf"
DEFAULT_PDF_EN = ROOT / "svar1_time_profiles_1pct_en.pdf"

PHE0_THICKNESS_MM = 2.540
TARGET_TIMES_S = tuple(range(1, 7))
CONTOUR_COLORS = {
    0.80: "#08357E",
    0.90: "#A04A00",
    0.95: "#7A0101",
}

TEXT = {
    "fr": {
        "sampled": r"Maximum échantillonné par ruban de 1\%",
        "interpolated": r"Ruban interpolé (aucun nœud)",
        "profile": r"Enveloppe radiale maximale",
        "contour": r"Profondeur du contour $\alpha={threshold}$",
        "panel_time": (
            r"cible : ${target}\,\mathrm{{s}}$ ; "
            r"état sauvegardé : ${saved}\,\mathrm{{s}}$"
        ),
        "depth": r"$d_{{{threshold}}}={depth}\,\mathrm{{mm}}$",
        "not_reached": r"$\alpha={threshold}$ non atteint",
        "xlabel": (
            r"Profondeur dans \texttt{phe0} depuis la face intérieure chaude [\%]"
        ),
        "ylabel": r"Maximum de SVAR1, $\alpha$",
        "secondary_xlabel": r"Profondeur radiale depuis la face chaude [$\mathrm{mm}$]",
    },
    "en": {
        "sampled": r"Sampled maximum in each 1\% band",
        "interpolated": r"Interpolated band (no result node)",
        "profile": r"Maximum radial envelope",
        "contour": r"Depth of the $\alpha={threshold}$ contour",
        "panel_time": (
            r"target: ${target}\,\mathrm{{s}}$; "
            r"saved state: ${saved}\,\mathrm{{s}}$"
        ),
        "depth": r"$d_{{{threshold}}}={depth}\,\mathrm{{mm}}$",
        "not_reached": r"$\alpha={threshold}$ not reached",
        "xlabel": r"Depth through \texttt{phe0} from the hot inner face [\%]",
        "ylabel": r"Maximum SVAR1, $\alpha$",
        "secondary_xlabel": r"Radial depth from the hot face [$\mathrm{mm}$]",
    },
}


def configure_matplotlib():
    """Apply the report style and use LaTeX for every visible label."""
    mpl_tmp = Path(tempfile.mkdtemp(prefix="mpl_svar1_time_profiles_"))
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_tmp))
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9.0,
            "text.usetex": True,
            "text.latex.preamble": (
                r"\usepackage[T1]{fontenc}"
                r"\usepackage[utf8]{inputenc}"
                r"\usepackage{lmodern}"
            ),
            "pgf.texsystem": "pdflatex",
            "pgf.rcfonts": False,
            "pgf.preamble": (
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
            "grid.alpha": 0.22,
            "grid.color": "#7f7f7f",
            "grid.linewidth": 0.5,
            "axes.axisbelow": True,
            "pdf.fonttype": 42,
        }
    )


def localized_number(value, decimals, language):
    """Format a number for a localized LaTeX label."""
    text = ("{:.%df}" % decimals).format(value)
    return text.replace(".", ",") if language == "fr" else text


def load_profiles(path):
    """Read and validate the six one-percent profiles from the DPF CSV."""
    grouped = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            grouped[int(float(row["target_time_s"]))].append(row)

    profiles = []
    for target_time in TARGET_TIMES_S:
        rows = sorted(
            grouped[target_time],
            key=lambda row: int(row["bin_index"]),
        )
        if len(rows) != 100:
            raise RuntimeError(
                "Expected 100 radial bands at {} s, found {}.".format(
                    target_time,
                    len(rows),
                )
            )

        indices = np.arange(100, dtype=int)
        raw = np.asarray(
            [
                float(row["raw_max_svar1"])
                if row["raw_max_svar1"]
                else np.nan
                for row in rows
            ],
            dtype=float,
        )
        plotted = np.asarray(
            [float(row["plotted_max_svar1"]) for row in rows],
            dtype=float,
        )
        contours = {
            threshold: float(rows[0]["contour_{}_depth_mm".format(key)])
            for threshold, key in ((0.80, "080"), (0.90, "090"), (0.95, "095"))
        }
        profiles.append(
            {
                "target_time": target_time,
                "saved_time": float(rows[0]["saved_time_s"]),
                "indices": indices,
                "centers": indices.astype(float) + 0.5,
                "raw": raw,
                "plotted": plotted,
                "contours": contours,
            }
        )
    return profiles


def plot_profiles(path, profiles, language):
    """Generate one localized six-panel vector PDF."""
    text = TEXT[language]
    fig, axes = plt.subplots(
        len(profiles),
        1,
        figsize=(8.2, 12.0),
        sharex=True,
    )

    for panel_index, (ax, profile) in enumerate(zip(axes, profiles)):
        centers = profile["centers"]
        raw = profile["raw"]
        plotted = profile["plotted"]
        sampled = np.isfinite(raw)
        interpolated = ~sampled

        ax.bar(
            centers[sampled],
            plotted[sampled],
            width=0.96,
            color="#9CBCE8",
            edgecolor="#315B91",
            linewidth=0.18,
            zorder=2,
        )
        ax.bar(
            centers[interpolated],
            plotted[interpolated],
            width=0.96,
            color="#E4E4E4",
            edgecolor="#666666",
            linewidth=0.35,
            hatch="////",
            zorder=2,
        )
        ax.step(
            centers,
            plotted,
            where="mid",
            color="#08357E",
            linewidth=1.25,
            zorder=3,
        )

        contour_labels = []
        for threshold, depth_mm in profile["contours"].items():
            threshold_label = localized_number(threshold, 2, language)
            if math.isfinite(depth_mm):
                depth_percent = 100.0 * depth_mm / PHE0_THICKNESS_MM
                color = CONTOUR_COLORS[threshold]
                ax.vlines(
                    depth_percent,
                    0.0,
                    threshold,
                    colors=color,
                    linestyles=":",
                    linewidth=0.9,
                    alpha=0.92,
                    zorder=4,
                )
                ax.plot(
                    depth_percent,
                    threshold,
                    marker="o",
                    color=color,
                    markersize=3.6,
                    zorder=5,
                )
                contour_labels.append(
                    text["depth"].format(
                        threshold=threshold_label,
                        depth=localized_number(depth_mm, 3, language),
                    )
                )
            else:
                contour_labels.append(
                    text["not_reached"].format(threshold=threshold_label)
                )

        ax.text(
            0.012,
            0.91,
            text["panel_time"].format(
                target=localized_number(profile["target_time"], 0, language),
                saved=localized_number(profile["saved_time"], 4, language),
            ),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=8.3,
            bbox={
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.86,
                "pad": 0.7,
            },
        )
        ax.text(
            0.985,
            0.91,
            r"\quad ".join(contour_labels),
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7.3,
            bbox={
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.86,
                "pad": 0.7,
            },
        )

        ax.set_xlim(0.0, 100.0)
        ax.set_ylim(0.0, 1.045)
        ax.set_yticks((0.0, 0.5, 1.0))
        ax.set_xticks(np.arange(0.0, 101.0, 10.0))
        if language == "fr":
            ax.yaxis.set_major_formatter(
                FuncFormatter(
                    lambda value, _: localized_number(value, 1, language)
                )
            )
        if panel_index == 0:
            def percent_to_mm(percent):
                return np.asarray(percent) * PHE0_THICKNESS_MM / 100.0

            def mm_to_percent(depth_mm):
                return np.asarray(depth_mm) * 100.0 / PHE0_THICKNESS_MM

            secondary = ax.secondary_xaxis(
                "top",
                functions=(percent_to_mm, mm_to_percent),
            )
            secondary.set_xlabel(text["secondary_xlabel"], labelpad=5)
            secondary.set_xticks(
                np.linspace(0.0, PHE0_THICKNESS_MM, 6)
            )
            secondary.xaxis.set_major_formatter(
                FuncFormatter(
                    lambda value, _: localized_number(value, 3, language)
                )
            )

    fig.supxlabel(text["xlabel"], y=0.016)
    fig.supylabel(text["ylabel"], x=0.018)

    legend_handles = [
        Patch(
            facecolor="#9CBCE8",
            edgecolor="#315B91",
            label=text["sampled"],
        ),
        Patch(
            facecolor="#E4E4E4",
            edgecolor="#666666",
            hatch="////",
            label=text["interpolated"],
        ),
        plt.Line2D(
            [0],
            [0],
            color="#08357E",
            linewidth=1.25,
            label=text["profile"],
        ),
    ]
    for threshold, color in CONTOUR_COLORS.items():
        legend_handles.append(
            plt.Line2D(
                [0],
                [0],
                color=color,
                linestyle=":",
                marker="o",
                markersize=3.6,
                linewidth=0.9,
                label=text["contour"].format(
                    threshold=localized_number(threshold, 2, language)
                ),
            )
        )
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.995),
        ncol=3,
        frameon=True,
        framealpha=0.96,
        fontsize=7.7,
    )
    fig.subplots_adjust(
        left=0.10,
        right=0.985,
        bottom=0.055,
        top=0.930,
        hspace=0.18,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    # The ordinary PDF backend keeps the TeX-rendered labels as vector text
    # while avoiding occasional filled-path corruption seen with the PGF
    # backend when this dense six-panel figure is rendered repeatedly.
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--pdf-fr", type=Path, default=DEFAULT_PDF_FR)
    parser.add_argument("--pdf-en", type=Path, default=DEFAULT_PDF_EN)
    parser.add_argument(
        "--language",
        choices=tuple(TEXT),
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.language:
        configure_matplotlib()
        profiles = load_profiles(args.csv)
        target = args.pdf_fr if args.language == "fr" else args.pdf_en
        with tempfile.TemporaryDirectory(
            prefix=".svar1_time_pdf_",
            dir=target.parent,
        ) as temporary:
            temporary_pdf = Path(temporary) / target.name
            plot_profiles(
                temporary_pdf,
                profiles,
                args.language,
            )
            os.replace(temporary_pdf, target)
        print("wrote {}".format(target))
        return

    common_arguments = (
        "--csv",
        str(args.csv),
        "--pdf-fr",
        str(args.pdf_fr),
        "--pdf-en",
        str(args.pdf_en),
    )
    for language in ("fr", "en"):
        subprocess.run(
            (
                sys.executable,
                str(Path(__file__).resolve()),
                "--language",
                language,
            )
            + common_arguments,
            check=True,
        )


if __name__ == "__main__":
    main()

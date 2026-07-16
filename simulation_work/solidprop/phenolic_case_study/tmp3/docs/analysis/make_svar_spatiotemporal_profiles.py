#!/usr/bin/env python3
"""Plot radial SVAR2 and axial SVAR1/SVAR2 profiles near each integer second.

The input CSV files are produced by
``dpf_extract_svar_spatiotemporal_profiles.py`` from the distributed ANSYS
``file*.rth`` result partitions. All plotted curves are maximum envelopes:

* radial profiles maximize over circumference and axial position in each
  one-percent radial band through ``phe0``;
* axial profiles maximize over nodes on the hot inner surface of ``phe0`` in
  each one-percent axial band, with distance measured from the lower cut plane
  of the 50 mm Mechanical slice.

Separate French and English vector PDFs are generated for all three studies.
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
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402


ROOT = Path(__file__).resolve().parent
DEFAULT_RADIAL_CSV = ROOT / "svar_radial_time_profiles_1pct.csv"
DEFAULT_AXIAL_CSV = ROOT / "svar_axial_time_profiles_1pct.csv"
TARGET_TIMES_S = tuple(range(1, 7))

OUTPUTS = {
    ("radial", 2, "fr"): ROOT / "svar2_radial_time_profiles_1pct_fr.pdf",
    ("radial", 2, "en"): ROOT / "svar2_radial_time_profiles_1pct_en.pdf",
    ("axial", 1, "fr"): ROOT / "svar1_axial_time_profiles_1pct_fr.pdf",
    ("axial", 1, "en"): ROOT / "svar1_axial_time_profiles_1pct_en.pdf",
    ("axial", 2, "fr"): ROOT / "svar2_axial_time_profiles_1pct_fr.pdf",
    ("axial", 2, "en"): ROOT / "svar2_axial_time_profiles_1pct_en.pdf",
}

STYLE = {
    1: {
        "fill": "#9CBCE8",
        "edge": "#315B91",
        "line": "#08357E",
    },
    2: {
        "fill": "#E8B18F",
        "edge": "#A04A00",
        "line": "#7A2E00",
    },
}

TEXT = {
    "fr": {
        "sampled": r"Maximum échantillonné par ruban de 1\%",
        "interpolated": r"Ruban interpolé (aucun nœud)",
        "radial_profile": r"Enveloppe radiale maximale",
        "axial_profile": r"Enveloppe axiale sur la face chaude",
        "panel_time": (
            r"cible : ${target}\,\mathrm{{s}}$ ; "
            r"état sauvegardé : ${saved}\,\mathrm{{s}}$"
        ),
        "radial_summary": (
            r"$\max={maximum}\,\mathrm{{s^{{-1}}}}$ à "
            r"$d={position}\,\mathrm{{mm}}$"
        ),
        "axial_summary_svar1": (
            r"plage axiale : ${minimum}$--${maximum}$ ; "
            r"étendue relative : ${spread}\,\%$"
        ),
        "axial_summary_svar2": (
            r"plage axiale : ${minimum}$--${maximum}\,\mathrm{{s^{{-1}}}}$ ; "
            r"étendue relative : ${spread}\,\%$"
        ),
        "radial_xlabel": (
            r"Profondeur dans \texttt{phe0} depuis la face intérieure chaude [\%]"
        ),
        "radial_secondary": (
            r"Profondeur radiale depuis la face chaude [$\mathrm{mm}$]"
        ),
        "axial_xlabel": (
            r"Distance depuis le plan inférieur du tronçon maillé "
            r"[$\mathrm{mm}$]"
        ),
        "axial_secondary": r"Position sur la longueur du tronçon [\%]",
        "radial_ylabel_svar2": (
            r"Maximum radial de SVAR2, $\dot{\alpha}$ "
            r"[$\mathrm{s^{-1}}$]"
        ),
        "axial_ylabel_svar1": (
            r"Maximum axial de SVAR1 sur la face chaude, $\alpha$"
        ),
        "axial_ylabel_svar2": (
            r"Maximum axial de SVAR2 sur la face chaude, $\dot{\alpha}$ "
            r"[$\mathrm{s^{-1}}$]"
        ),
    },
    "en": {
        "sampled": r"Sampled maximum in each 1\% band",
        "interpolated": r"Interpolated band (no result node)",
        "radial_profile": r"Maximum radial envelope",
        "axial_profile": r"Hot-face axial envelope",
        "panel_time": (
            r"target: ${target}\,\mathrm{{s}}$; "
            r"saved state: ${saved}\,\mathrm{{s}}$"
        ),
        "radial_summary": (
            r"$\max={maximum}\,\mathrm{{s^{{-1}}}}$ at "
            r"$d={position}\,\mathrm{{mm}}$"
        ),
        "axial_summary_svar1": (
            r"axial range: ${minimum}$--${maximum}$; "
            r"relative span: ${spread}\,\%$"
        ),
        "axial_summary_svar2": (
            r"axial range: ${minimum}$--${maximum}\,\mathrm{{s^{{-1}}}}$; "
            r"relative span: ${spread}\,\%$"
        ),
        "radial_xlabel": (
            r"Depth through \texttt{phe0} from the hot inner face [\%]"
        ),
        "radial_secondary": r"Radial depth from the hot face [$\mathrm{mm}$]",
        "axial_xlabel": (
            r"Distance from the lower plane of the meshed slice "
            r"[$\mathrm{mm}$]"
        ),
        "axial_secondary": r"Position along the slice length [\%]",
        "radial_ylabel_svar2": (
            r"Maximum radial SVAR2, $\dot{\alpha}$ "
            r"[$\mathrm{s^{-1}}$]"
        ),
        "axial_ylabel_svar1": (
            r"Maximum axial hot-face SVAR1, $\alpha$"
        ),
        "axial_ylabel_svar2": (
            r"Maximum axial hot-face SVAR2, $\dot{\alpha}$ "
            r"[$\mathrm{s^{-1}}$]"
        ),
    },
}


def configure_matplotlib():
    """Apply the report style and use LaTeX for visible labels."""
    mpl_tmp = Path(tempfile.mkdtemp(prefix="mpl_svar_profiles_"))
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


def localized_physical_value(value, language):
    """Format small physical values without losing them to decimal rounding."""
    if value == 0.0:
        return "0"
    if abs(value) >= 1.0e-3:
        return localized_number(value, 4, language)
    exponent = int(math.floor(math.log10(abs(value))))
    mantissa = value / (10.0 ** exponent)
    return r"{}\times 10^{{{}}}".format(
        localized_number(mantissa, 2, language),
        exponent,
    )


def load_profiles(path, axis, svar_index):
    """Read and validate the six profiles for one axis and state variable."""
    grouped = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if int(row["svar_index"]) != svar_index:
                continue
            grouped[int(float(row["target_time_s"]))].append(row)

    profiles = []
    for target_time in TARGET_TIMES_S:
        rows = sorted(
            grouped[target_time],
            key=lambda row: int(row["bin_index"]),
        )
        if len(rows) != 100:
            raise RuntimeError(
                "Expected 100 {} bands for SVAR{} at {} s, found {}."
                .format(axis, svar_index, target_time, len(rows))
            )

        prefix = "radial_depth" if axis == "radial" else "axial_distance"
        starts = np.asarray(
            [float(row["{}_mm_start".format(prefix)]) for row in rows],
            dtype=float,
        )
        ends = np.asarray(
            [float(row["{}_mm_end".format(prefix)]) for row in rows],
            dtype=float,
        )
        raw = np.asarray(
            [
                float(row["raw_max_value"])
                if row["raw_max_value"]
                else np.nan
                for row in rows
            ],
            dtype=float,
        )
        plotted = np.asarray(
            [float(row["plotted_max_value"]) for row in rows],
            dtype=float,
        )
        profiles.append(
            {
                "target_time": target_time,
                "saved_time": float(rows[0]["saved_time_s"]),
                "centers_mm": 0.5 * (starts + ends),
                "widths_mm": ends - starts,
                "extent_mm": float(ends[-1]),
                "raw": raw,
                "plotted": plotted,
            }
        )
    return profiles


def nice_rate_limit(profiles):
    """Return a shared rounded upper limit for SVAR2 panels."""
    maximum = max(float(np.nanmax(profile["plotted"])) for profile in profiles)
    if maximum <= 0.0:
        return 1.0
    magnitude = 10.0 ** math.floor(math.log10(maximum))
    normalized = maximum / magnitude
    for candidate in (1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0):
        if normalized <= candidate:
            return 1.04 * candidate * magnitude
    return 1.04 * maximum


def axis_summary(profile, axis, svar_index, language):
    """Return the compact annotation for one panel."""
    text = TEXT[language]
    values = profile["plotted"]
    maximum = float(np.nanmax(values))
    minimum = float(np.nanmin(values))
    if axis == "radial":
        max_index = int(np.nanargmax(values))
        position = float(profile["centers_mm"][max_index])
        return text["radial_summary"].format(
            maximum=localized_number(maximum, 4, language),
            position=localized_number(position, 3, language),
        )

    spread = 0.0 if maximum == 0.0 else 100.0 * (maximum - minimum) / maximum
    if svar_index == 2:
        minimum_text = localized_physical_value(minimum, language)
        maximum_text = localized_physical_value(maximum, language)
    else:
        minimum_text = localized_number(minimum, 5, language)
        maximum_text = localized_number(maximum, 5, language)
    return text["axial_summary_svar{}".format(svar_index)].format(
        minimum=minimum_text,
        maximum=maximum_text,
        spread=localized_number(spread, 2, language),
    )


def plot_profiles(path, profiles, axis, svar_index, language):
    """Generate one localized six-panel vector PDF."""
    text = TEXT[language]
    style = STYLE[svar_index]
    fig, axes = plt.subplots(
        len(profiles),
        1,
        figsize=(8.2, 12.0),
        sharex=True,
    )
    y_limit = 1.045 if svar_index == 1 else nice_rate_limit(profiles)

    for panel_index, (ax, profile) in enumerate(zip(axes, profiles)):
        centers = profile["centers_mm"]
        widths = profile["widths_mm"]
        raw = profile["raw"]
        plotted = profile["plotted"]
        sampled = np.isfinite(raw)
        interpolated = ~sampled

        ax.bar(
            centers[sampled],
            plotted[sampled],
            width=0.96 * widths[sampled],
            color=style["fill"],
            edgecolor=style["edge"],
            linewidth=0.18,
            zorder=2,
        )
        ax.bar(
            centers[interpolated],
            plotted[interpolated],
            width=0.96 * widths[interpolated],
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
            color=style["line"],
            linewidth=1.25,
            zorder=3,
        )
        max_index = int(np.nanargmax(plotted))
        ax.plot(
            centers[max_index],
            plotted[max_index],
            marker="o",
            color=style["line"],
            markersize=3.8,
            zorder=4,
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
            axis_summary(profile, axis, svar_index, language),
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7.7,
            bbox={
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.86,
                "pad": 0.7,
            },
        )

        ax.set_xlim(0.0, profile["extent_mm"])
        panel_y_limit = y_limit
        if axis == "axial" and svar_index == 2:
            panel_y_limit = 1.08 * float(np.nanmax(plotted))
        ax.set_ylim(0.0, panel_y_limit)
        if svar_index == 1:
            ax.set_yticks((0.0, 0.5, 1.0))
        else:
            ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
            if axis == "axial":
                ax.yaxis.set_major_formatter(
                    FuncFormatter(
                        lambda value, _: (
                            "$0$"
                            if value == 0.0
                            else "${}$".format(
                                localized_physical_value(value, language)
                            )
                        )
                    )
                )
        if language == "fr":
            if not (axis == "axial" and svar_index == 2):
                ax.yaxis.set_major_formatter(
                    FuncFormatter(
                        lambda value, _: localized_number(value, 2, language)
                    )
                )

        if panel_index == 0:
            extent = profile["extent_mm"]
            if axis == "radial":
                def bottom_to_top(distance_mm):
                    return 100.0 * np.asarray(distance_mm) / extent

                def top_to_bottom(percent):
                    return extent * np.asarray(percent) / 100.0

                secondary_label = text["radial_secondary"]
                secondary_ticks = np.linspace(0.0, 100.0, 6)
                secondary_formatter = FuncFormatter(
                    lambda value, _: localized_number(
                        extent * value / 100.0,
                        3,
                        language,
                    )
                )
            else:
                def bottom_to_top(distance_mm):
                    return 100.0 * np.asarray(distance_mm) / extent

                def top_to_bottom(percent):
                    return extent * np.asarray(percent) / 100.0

                secondary_label = text["axial_secondary"]
                secondary_ticks = np.linspace(0.0, 100.0, 6)
                secondary_formatter = FuncFormatter(
                    lambda value, _: localized_number(value, 0, language)
                )

            secondary = ax.secondary_xaxis(
                "top",
                functions=(bottom_to_top, top_to_bottom),
            )
            secondary.set_xlabel(secondary_label, labelpad=5)
            secondary.set_xticks(secondary_ticks)
            secondary.xaxis.set_major_formatter(secondary_formatter)

    if axis == "radial":
        xlabel = text["radial_xlabel"]
        # The primary radial axis in this companion plot is percent, matching
        # the original SVAR1 figure. Re-label its millimetre coordinates.
        extent = profiles[0]["extent_mm"]
        for ax in axes:
            ticks_percent = np.arange(0.0, 101.0, 10.0)
            ax.set_xticks(extent * ticks_percent / 100.0)
            ax.xaxis.set_major_formatter(
                FuncFormatter(
                    lambda value, _: localized_number(
                        100.0 * value / extent,
                        0,
                        language,
                    )
                )
            )
    else:
        xlabel = text["axial_xlabel"]
        axes[-1].set_xticks(np.linspace(0.0, profiles[0]["extent_mm"], 11))
        if language == "fr":
            axes[-1].xaxis.set_major_formatter(
                FuncFormatter(
                    lambda value, _: localized_number(value, 0, language)
                )
            )

    ylabel = text["{}_ylabel_svar{}".format(axis, svar_index)]
    fig.supxlabel(xlabel, y=0.016)
    fig.supylabel(ylabel, x=0.018)

    profile_label = text["{}_profile".format(axis)]
    legend_handles = [
        Patch(
            facecolor=style["fill"],
            edgecolor=style["edge"],
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
            color=style["line"],
            linewidth=1.25,
            marker="o",
            markersize=3.8,
            label=profile_label,
        ),
    ]
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.992),
        ncol=3,
        frameon=True,
        framealpha=0.96,
        fontsize=8.0,
    )
    fig.subplots_adjust(
        left=0.17 if axis == "axial" and svar_index == 2 else 0.10,
        right=0.985,
        bottom=0.055,
        top=0.930,
        hspace=0.18,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radial-csv", type=Path, default=DEFAULT_RADIAL_CSV)
    parser.add_argument("--axial-csv", type=Path, default=DEFAULT_AXIAL_CSV)
    parser.add_argument("--axis", choices=("radial", "axial"))
    parser.add_argument("--svar", choices=(1, 2), type=int)
    parser.add_argument("--language", choices=tuple(TEXT))
    return parser.parse_args()


def main():
    args = parse_args()
    if args.axis is not None:
        if args.svar is None or args.language is None:
            raise RuntimeError("--axis requires --svar and --language.")
        configure_matplotlib()
        source = args.radial_csv if args.axis == "radial" else args.axial_csv
        profiles = load_profiles(source, args.axis, args.svar)
        target = OUTPUTS[(args.axis, args.svar, args.language)]
        with tempfile.TemporaryDirectory(
            prefix=".svar_profile_pdf_",
            dir=target.parent,
        ) as temporary:
            temporary_pdf = Path(temporary) / target.name
            plot_profiles(
                temporary_pdf,
                profiles,
                args.axis,
                args.svar,
                args.language,
            )
            os.replace(temporary_pdf, target)
        print("wrote {}".format(target))
        return

    jobs = (
        ("radial", 2, "fr"),
        ("radial", 2, "en"),
        ("axial", 1, "fr"),
        ("axial", 1, "en"),
        ("axial", 2, "fr"),
        ("axial", 2, "en"),
    )
    common_arguments = (
        "--radial-csv",
        str(args.radial_csv),
        "--axial-csv",
        str(args.axial_csv),
    )
    for axis, svar_index, language in jobs:
        subprocess.run(
            (
                sys.executable,
                str(Path(__file__).resolve()),
                "--axis",
                axis,
                "--svar",
                str(svar_index),
                "--language",
                language,
            )
            + common_arguments,
            check=True,
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate the Simulation 2 SVAR profile figures in French and English.

The radial and axial CSV files are produced by
``dpf_extract_svar_spatiotemporal_profiles.py`` from the ten distributed RTH
partitions.  This script reproduces the five figure families used for
Simulation 1:

* last extracted radial SVAR1 profile;
* radial SVAR1 profiles near 1--6 s;
* radial SVAR2 profiles near 1--6 s;
* axial hot-surface SVAR1 profiles near 1--6 s; and
* axial hot-surface SVAR2 profiles near 1--6 s.

Empty one-percent bins are retained as missing observations, hatched, and
filled only for the plotted envelope by linear interpolation.  Every radial
panel also shows the cumulative virtual-recession position read from the
Simulation 2 controller history.  The line therefore represents the
energy-balance recession coordinate, not a contour inferred from SVAR1.
"""

import argparse
import csv
import math
import os
import tempfile
from collections import defaultdict
from pathlib import Path

import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402


ROOT = Path(__file__).resolve().parent
DEFAULT_RADIAL_CSV = ROOT / "simulation2_svar_radial_time_profiles_1pct.csv"
DEFAULT_AXIAL_CSV = ROOT / "simulation2_svar_axial_time_profiles_1pct.csv"
DEFAULT_HISTORY_CSV = ROOT / "simulation2_history_svar_snapshot.csv"
DEFAULT_CONTOUR_DISTANCE_CSV = (
    ROOT / "simulation2_recession_to_pyrolysis_contours_vs_time.csv"
)
TARGET_TIMES_S = tuple(range(1, 7))
PHE0_THICKNESS_MM = 2.540
RECESSION_ONSET_MM = 0.001

OUTPUTS = {
    ("last_radial", 1, "fr"): ROOT / "simulation2_svar1_radial_profile_1pct_fr.pdf",
    ("last_radial", 1, "en"): ROOT / "simulation2_svar1_radial_profile_1pct_en.pdf",
    ("radial", 1, "fr"): ROOT / "simulation2_svar1_radial_time_profiles_1pct_fr.pdf",
    ("radial", 1, "en"): ROOT / "simulation2_svar1_radial_time_profiles_1pct_en.pdf",
    ("radial", 2, "fr"): ROOT / "simulation2_svar2_radial_time_profiles_1pct_fr.pdf",
    ("radial", 2, "en"): ROOT / "simulation2_svar2_radial_time_profiles_1pct_en.pdf",
    ("axial", 1, "fr"): ROOT / "simulation2_svar1_axial_time_profiles_1pct_fr.pdf",
    ("axial", 1, "en"): ROOT / "simulation2_svar1_axial_time_profiles_1pct_en.pdf",
    ("axial", 2, "fr"): ROOT / "simulation2_svar2_axial_time_profiles_1pct_fr.pdf",
    ("axial", 2, "en"): ROOT / "simulation2_svar2_axial_time_profiles_1pct_en.pdf",
    ("contour_distance", 1, "fr"): (
        ROOT / "simulation2_recession_to_pyrolysis_contours_vs_time_fr.pdf"
    ),
    ("contour_distance", 1, "en"): (
        ROOT / "simulation2_recession_to_pyrolysis_contours_vs_time_en.pdf"
    ),
}

STYLE = {
    1: {"fill": "#9CBCE8", "edge": "#315B91", "line": "#08357E"},
    2: {"fill": "#E8B18F", "edge": "#A04A00", "line": "#7A2E00"},
}
RECESSION_COLOR = "#2F6B3D"
CONTOUR_COLORS = {
    0.80: "#08357E",
    0.90: "#A04A00",
    0.95: "#7A0101",
    0.99: "#4C3C91",
}
CONTOUR_DISTANCE_STYLES = {
    0.99: {"color": "#4C3C91", "marker": "o", "linestyle": "-"},
    0.95: {"color": "#A04A00", "marker": "s", "linestyle": "--"},
    0.90: {"color": "#2F6B3D", "marker": "^", "linestyle": "-."},
}
RECESSION_ONSET_COLOR = "#7A0101"

TEXT = {
    "fr": {
        "sampled": r"Maximum échantillonné par ruban de 1\%",
        "interpolated": r"Ruban interpolé (aucun nœud)",
        "profile": r"Enveloppe maximale",
        "recession": r"Ligne de récession virtuelle",
        "panel_time": (
            r"cible : ${target}\,\mathrm{{s}}$ ; "
            r"état sauvegardé : ${saved}\,\mathrm{{s}}$"
        ),
        "recession_value": r"$s={value}\,\mathrm{{mm}}$",
        "radial_summary": (
            r"$\max={maximum}$ à $d={position}\,\mathrm{{mm}}$ ; "
            r"$s={recession}\,\mathrm{{mm}}$"
        ),
        "axial_summary": (
            r"plage : ${minimum}$--${maximum}$ ; "
            r"étendue relative : ${spread}\,\%$"
        ),
        "radial_xlabel": (
            r"Profondeur dans \texttt{phe0} depuis la face chaude "
            r"[$\mathrm{mm}$]"
        ),
        "radial_secondary": r"Profondeur dans \texttt{phe0} [\%]",
        "axial_xlabel": (
            r"Distance depuis le plan inférieur du tronçon maillé "
            r"[$\mathrm{mm}$]"
        ),
        "axial_secondary": r"Position sur la longueur du tronçon [\%]",
        "ylabel_svar1_radial": r"Maximum radial de SVAR1, $\alpha$",
        "ylabel_svar2_radial": (
            r"Maximum radial de SVAR2, $\dot{\alpha}$ [$\mathrm{s^{-1}}$]"
        ),
        "ylabel_svar1_axial": (
            r"Maximum axial de SVAR1 sur la face chaude, $\alpha$"
        ),
        "ylabel_svar2_axial": (
            r"Maximum axial de SVAR2 sur la face chaude, "
            r"$\dot{\alpha}$ [$\mathrm{s^{-1}}$]"
        ),
        "last_title": (
            r"Simulation 2 : profil radial de SVAR1 au dernier état extrait"
            "\n"
            r"$t={time}\,\mathrm{{s}}$ ; ligne de récession "
            r"$s={recession}\,\mathrm{{mm}}$"
        ),
        "contour": r"Contour $\alpha={threshold}$",
        "contour_value": r"$d_{{{threshold}}}={depth}\,\mathrm{{mm}}$",
        "not_reached": r"$\alpha={threshold}$ non atteint",
        "distance_title": (
            r"Simulation 2 : écart radial entre la récession virtuelle"
            "\n"
            r"et les contours de conversion pyrolytique"
        ),
        "distance_xlabel": r"Temps physique [$\mathrm{s}$]",
        "distance_ylabel": (
            r"Écart signé $d_{\alpha}-s$ [$\mathrm{mm}$]"
        ),
        "distance_legend": r"Contour $\alpha={threshold}\,\%$",
        "distance_note": (
            r"{count} états exacts, $\Delta t={interval}\,\mathrm{{s}}$. "
            r"Positif : contour plus profond."
        ),
        "recession_onset": (
            r"Début de récession ($s\geq 1\,\mathrm{{\mu m}}$) : "
            r"$t={time}\,\mathrm{{s}}$"
        ),
    },
    "en": {
        "sampled": r"Sampled maximum in each 1\% band",
        "interpolated": r"Interpolated band (no result node)",
        "profile": r"Maximum envelope",
        "recession": r"Virtual-recession line",
        "panel_time": (
            r"target: ${target}\,\mathrm{{s}}$; "
            r"saved state: ${saved}\,\mathrm{{s}}$"
        ),
        "recession_value": r"$s={value}\,\mathrm{{mm}}$",
        "radial_summary": (
            r"$\max={maximum}$ at $d={position}\,\mathrm{{mm}}$; "
            r"$s={recession}\,\mathrm{{mm}}$"
        ),
        "axial_summary": (
            r"range: ${minimum}$--${maximum}$; "
            r"relative span: ${spread}\,\%$"
        ),
        "radial_xlabel": (
            r"Depth through \texttt{phe0} from the hot face "
            r"[$\mathrm{mm}$]"
        ),
        "radial_secondary": r"Depth through \texttt{phe0} [\%]",
        "axial_xlabel": (
            r"Distance from the lower plane of the meshed slice "
            r"[$\mathrm{mm}$]"
        ),
        "axial_secondary": r"Position along the slice [\%]",
        "ylabel_svar1_radial": r"Maximum radial SVAR1, $\alpha$",
        "ylabel_svar2_radial": (
            r"Maximum radial SVAR2, $\dot{\alpha}$ [$\mathrm{s^{-1}}$]"
        ),
        "ylabel_svar1_axial": r"Maximum axial hot-face SVAR1, $\alpha$",
        "ylabel_svar2_axial": (
            r"Maximum axial hot-face SVAR2, "
            r"$\dot{\alpha}$ [$\mathrm{s^{-1}}$]"
        ),
        "last_title": (
            r"Simulation 2: radial SVAR1 profile at the latest extracted state"
            "\n"
            r"$t={time}\,\mathrm{{s}}$; recession line "
            r"$s={recession}\,\mathrm{{mm}}$"
        ),
        "contour": r"$\alpha={threshold}$ contour",
        "contour_value": r"$d_{{{threshold}}}={depth}\,\mathrm{{mm}}$",
        "not_reached": r"$\alpha={threshold}$ not reached",
        "distance_title": (
            r"Simulation 2: radial separation between virtual recession"
            "\n"
            r"and pyrolysis-conversion contours"
        ),
        "distance_xlabel": r"Physical time [$\mathrm{s}$]",
        "distance_ylabel": (
            r"Signed separation $d_{\alpha}-s$ [$\mathrm{mm}$]"
        ),
        "distance_legend": r"$\alpha={threshold}\,\%$ contour",
        "distance_note": (
            r"{count} exact states, $\Delta t={interval}\,\mathrm{{s}}$. "
            r"Positive: deeper contour."
        ),
        "recession_onset": (
            r"Recession onset ($s\geq 1\,\mathrm{{\mu m}}$): "
            r"$t={time}\,\mathrm{{s}}$"
        ),
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radial-csv", type=Path, default=DEFAULT_RADIAL_CSV)
    parser.add_argument("--axial-csv", type=Path, default=DEFAULT_AXIAL_CSV)
    parser.add_argument("--history-csv", type=Path, default=DEFAULT_HISTORY_CSV)
    parser.add_argument(
        "--contour-only",
        action="store_true",
        help="Regenerate only the bilingual contour-separation figures.",
    )
    return parser.parse_args()


def configure_matplotlib():
    mpl_tmp = Path(tempfile.mkdtemp(prefix="mpl_sim2_svar_"))
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
            "axes.titlecolor": "#111111",
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
    result = ("{:.%df}" % decimals).format(value)
    return result.replace(".", ",") if language == "fr" else result


def localized_value(value, language):
    if value == 0.0:
        return "0"
    if abs(value) >= 1.0e-3:
        return localized_number(value, 4, language)
    exponent = int(math.floor(math.log10(abs(value))))
    mantissa = value / (10.0**exponent)
    return r"{}\times 10^{{{}}}".format(
        localized_number(mantissa, 2, language),
        exponent,
    )


def read_history(path):
    data = np.genfromtxt(path, names=True, dtype=float, encoding="utf-8")
    data = np.atleast_1d(data)
    required = {"time_s", "recession_m"}
    if not required.issubset(data.dtype.names or ()):
        raise RuntimeError("Unexpected Simulation 2 history columns.")
    return data


def recession_at(history, saved_time):
    index = int(np.argmin(np.abs(history["time_s"] - saved_time)))
    if abs(float(history["time_s"][index]) - saved_time) > 1.0e-7:
        raise RuntimeError(
            "No controller history row matches saved time {:.12g} s.".format(
                saved_time
            )
        )
    return 1000.0 * float(history["recession_m"][index])


def load_profiles(path, axis, svar_index, history):
    grouped = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if int(row["svar_index"]) == svar_index:
                grouped[float(row["target_time_s"])].append(row)

    prefix = "radial_depth" if axis == "radial" else "axial_distance"

    def build_profile(target_time):
        matching_time = min(grouped, key=lambda value: abs(value - target_time))
        if abs(matching_time - target_time) > 1.0e-8:
            raise RuntimeError(
                "No {} SVAR{} profile matches target time {:.12g} s.".format(
                    axis, svar_index, target_time
                )
            )
        rows = sorted(
            grouped[matching_time], key=lambda row: int(row["bin_index"])
        )
        if len(rows) != 100:
            raise RuntimeError(
                "Expected 100 {} bands for SVAR{} at {} s, found {}.".format(
                    axis, svar_index, target_time, len(rows)
                )
            )
        starts = np.asarray(
            [float(row["{}_mm_start".format(prefix)]) for row in rows]
        )
        ends = np.asarray(
            [float(row["{}_mm_end".format(prefix)]) for row in rows]
        )
        raw = np.asarray(
            [
                float(row["raw_max_value"]) if row["raw_max_value"] else np.nan
                for row in rows
            ]
        )
        saved_time = float(rows[0]["saved_time_s"])
        return {
            "target_time": matching_time,
            "saved_time": saved_time,
            "centers": 0.5 * (starts + ends),
            "widths": ends - starts,
            "extent": float(ends[-1]),
            "raw": raw,
            "plotted": np.asarray(
                [float(row["plotted_max_value"]) for row in rows]
            ),
            "recession": recession_at(history, saved_time),
        }

    temporal = [build_profile(float(time)) for time in TARGET_TIMES_S]
    latest = build_profile(max(grouped))
    return temporal, latest


def contour_depth(profile, threshold):
    values = profile["plotted"]
    centers = profile["centers"]
    above = np.flatnonzero(values >= threshold)
    if above.size == 0:
        return math.nan
    last = int(above[-1])
    if last == values.size - 1:
        return float(centers[last])
    x0, x1 = float(centers[last]), float(centers[last + 1])
    y0, y1 = float(values[last]), float(values[last + 1])
    if y1 == y0:
        return x0
    return x0 + (threshold - y0) * (x1 - x0) / (y1 - y0)


def contour_distance_rows(profiles):
    rows = []
    for profile in sorted(profiles, key=lambda item: item["saved_time"]):
        row = {
            "saved_time_s": profile["saved_time"],
            "recession_depth_mm": profile["recession"],
        }
        for threshold in (0.99, 0.95, 0.90):
            key = "{:03d}".format(round(100.0 * threshold))
            depth = contour_depth(profile, threshold)
            row["contour_{}_depth_mm".format(key)] = depth
            row["signed_distance_{}_mm".format(key)] = (
                depth - profile["recession"] if math.isfinite(depth) else math.nan
            )
        rows.append(row)
    return rows


def write_contour_distance_csv(path, rows):
    fieldnames = [
        "saved_time_s",
        "recession_depth_mm",
        "contour_099_depth_mm",
        "signed_distance_099_mm",
        "contour_095_depth_mm",
        "signed_distance_095_mm",
        "contour_090_depth_mm",
        "signed_distance_090_mm",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        newline="",
        encoding="utf-8",
        dir=path.parent,
        prefix=".{}_".format(path.name),
        suffix=".tmp",
        delete=False,
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    name: (
                        ""
                        if isinstance(row[name], float)
                        and not math.isfinite(row[name])
                        else "{:.12g}".format(row[name])
                    )
                    for name in fieldnames
                }
            )
        temporary_path = Path(stream.name)
    temporary_path.replace(path)


def read_contour_distance_csv(path):
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for source in csv.DictReader(stream):
            row = {
                "saved_time_s": float(source["saved_time_s"]),
                "recession_depth_mm": float(source["recession_depth_mm"]),
            }
            for threshold in (0.99, 0.95, 0.90):
                key = "{:03d}".format(round(100.0 * threshold))
                for source_name in (
                    "contour_{}_depth_mm".format(key),
                    "signed_distance_{}_mm".format(key),
                ):
                    row[source_name] = (
                        float(source[source_name])
                        if source.get(source_name, "")
                        else math.nan
                    )
            rows.append(row)
    if not rows:
        raise RuntimeError("The contour-distance CSV is empty.")
    return sorted(rows, key=lambda row: row["saved_time_s"])


def recession_onset_time(history):
    recession_mm = 1000.0 * np.asarray(history["recession_m"], dtype=float)
    reached = np.flatnonzero(recession_mm >= RECESSION_ONSET_MM)
    if reached.size == 0:
        return math.nan
    return float(history["time_s"][int(reached[0])])


def plot_contour_distances(output, rows, history, language):
    text = TEXT[language]
    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    times = np.asarray([row["saved_time_s"] for row in rows], dtype=float)
    marker_interval = max(1, int(round(len(rows) / 14.0)))
    time_interval = float(np.median(np.diff(times))) if len(times) > 1 else math.nan

    for threshold in (0.99, 0.95, 0.90):
        key = "{:03d}".format(round(100.0 * threshold))
        distances = np.asarray(
            [row["signed_distance_{}_mm".format(key)] for row in rows],
            dtype=float,
        )
        style = CONTOUR_DISTANCE_STYLES[threshold]
        ax.plot(
            times,
            distances,
            color=style["color"],
            marker=style["marker"],
            linestyle=style["linestyle"],
            linewidth=1.8,
            markersize=5.2,
            markevery=marker_interval,
            label=text["distance_legend"].format(
                threshold=localized_number(100.0 * threshold, 0, language)
            ),
            zorder=3,
        )

    ax.axhline(0.0, color="#555555", linewidth=0.9, zorder=1)
    onset_time = recession_onset_time(history)
    if math.isfinite(onset_time):
        ax.axvline(
            onset_time,
            color=RECESSION_ONSET_COLOR,
            linestyle=":",
            linewidth=1.6,
            label=text["recession_onset"].format(
                time=localized_number(onset_time, 2, language)
            ),
            zorder=2,
        )
    ax.set_xlim(0.0, max(times) + 0.15)
    ax.set_xlabel(text["distance_xlabel"])
    ax.set_ylabel(text["distance_ylabel"])
    ax.set_title(text["distance_title"], pad=12)
    ax.legend(
        loc="upper left",
        frameon=True,
        framealpha=0.94,
        fontsize=8.0,
    )
    ax.text(
        0.985,
        0.035,
        text["distance_note"].format(
            count=len(rows),
            interval=(
                localized_number(time_interval, 2, language)
                if math.isfinite(time_interval)
                else "---"
            ),
        ),
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8.2,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.88},
    )
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    if language == "fr":
        ax.xaxis.set_major_formatter(
            FuncFormatter(
                lambda value, _: localized_number(value, 0, language)
            )
        )
        ax.yaxis.set_major_formatter(
            FuncFormatter(
                lambda value, _: localized_number(value, 2, language)
            )
        )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def draw_bands(ax, profile, svar_index):
    style = STYLE[svar_index]
    sampled = np.isfinite(profile["raw"])
    interpolated = ~sampled
    ax.bar(
        profile["centers"][sampled],
        profile["plotted"][sampled],
        width=0.96 * profile["widths"][sampled],
        color=style["fill"],
        edgecolor=style["edge"],
        linewidth=0.18,
        zorder=2,
    )
    ax.bar(
        profile["centers"][interpolated],
        profile["plotted"][interpolated],
        width=0.96 * profile["widths"][interpolated],
        color="#E4E4E4",
        edgecolor="#666666",
        linewidth=0.35,
        hatch="////",
        zorder=2,
    )
    ax.step(
        profile["centers"],
        profile["plotted"],
        where="mid",
        color=style["line"],
        linewidth=1.25,
        zorder=3,
    )


def add_recession_line(ax, profile):
    ax.axvline(
        profile["recession"],
        color=RECESSION_COLOR,
        linestyle="--",
        linewidth=1.35,
        zorder=5,
    )


def radial_summary(profile, language):
    maximum_index = int(np.nanargmax(profile["plotted"]))
    return TEXT[language]["radial_summary"].format(
        maximum=localized_number(
            float(profile["plotted"][maximum_index]), 4, language
        ),
        position=localized_number(
            float(profile["centers"][maximum_index]), 3, language
        ),
        recession=localized_number(profile["recession"], 3, language),
    )


def axial_summary(profile, language):
    maximum = float(np.nanmax(profile["plotted"]))
    minimum = float(np.nanmin(profile["plotted"]))
    spread = 0.0 if maximum == 0.0 else 100.0 * (maximum - minimum) / maximum
    return TEXT[language]["axial_summary"].format(
        minimum=localized_value(minimum, language),
        maximum=localized_value(maximum, language),
        spread=localized_number(spread, 2, language),
    )


def temporal_y_limit(profiles, svar_index):
    if svar_index == 1:
        return 1.045
    maximum = max(float(np.nanmax(profile["plotted"])) for profile in profiles)
    return 1.08 * maximum if maximum > 0.0 else 1.0


def add_secondary_axis(ax, extent, axis, language):
    secondary = ax.secondary_xaxis(
        "top",
        functions=(
            lambda distance: 100.0 * np.asarray(distance) / extent,
            lambda percent: extent * np.asarray(percent) / 100.0,
        ),
    )
    secondary.set_xticks(np.linspace(0.0, 100.0, 6))
    secondary.xaxis.set_major_formatter(
        FuncFormatter(
            lambda value, _: localized_number(value, 0, language)
        )
    )
    secondary.set_xlabel(
        TEXT[language]["{}_secondary".format(axis)],
        labelpad=5,
    )


def plot_temporal(output, profiles, axis, svar_index, language):
    text = TEXT[language]
    fig, axes = plt.subplots(6, 1, figsize=(8.2, 12.0), sharex=True)
    shared_limit = temporal_y_limit(profiles, svar_index)

    for panel_index, (ax, profile) in enumerate(zip(axes, profiles)):
        draw_bands(ax, profile, svar_index)
        if axis == "radial":
            add_recession_line(ax, profile)
            summary = radial_summary(profile, language)
        else:
            summary = axial_summary(profile, language)

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
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.86},
        )
        ax.text(
            0.985,
            0.91,
            summary,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7.6,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.86},
        )
        ax.set_xlim(0.0, profile["extent"])
        panel_limit = shared_limit
        if axis == "axial" and svar_index == 2:
            panel_limit = 1.08 * float(np.nanmax(profile["plotted"]))
        ax.set_ylim(0.0, panel_limit)
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
                            else "${}$".format(localized_value(value, language))
                        )
                    )
                )
        if language == "fr" and not (axis == "axial" and svar_index == 2):
            ax.yaxis.set_major_formatter(
                FuncFormatter(
                    lambda value, _: localized_number(value, 2, language)
                )
            )
        if panel_index == 0:
            add_secondary_axis(ax, profile["extent"], axis, language)

    axes[-1].set_xlabel(text["{}_xlabel".format(axis)])
    if language == "fr":
        axes[-1].xaxis.set_major_formatter(
            FuncFormatter(
                lambda value, _: localized_number(value, 2, language)
            )
        )
    fig.supylabel(text["ylabel_svar{}_{}".format(svar_index, axis)], x=0.017)
    legend_handles = [
        Patch(
            facecolor=STYLE[svar_index]["fill"],
            edgecolor=STYLE[svar_index]["edge"],
            label=text["sampled"],
        ),
        Patch(
            facecolor="#E4E4E4",
            edgecolor="#666666",
            hatch="////",
            label=text["interpolated"],
        ),
        Line2D(
            [0],
            [0],
            color=STYLE[svar_index]["line"],
            linewidth=1.25,
            label=text["profile"],
        ),
    ]
    if axis == "radial":
        legend_handles.append(
            Line2D(
                [0],
                [0],
                color=RECESSION_COLOR,
                linestyle="--",
                linewidth=1.35,
                label=text["recession"],
            )
        )
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=len(legend_handles),
        frameon=False,
        bbox_to_anchor=(0.5, 0.012),
    )
    fig.subplots_adjust(
        left=0.105,
        right=0.985,
        top=0.94,
        bottom=0.075,
        hspace=0.16,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def plot_last_radial(output, profile, language):
    text = TEXT[language]
    fig, ax = plt.subplots(figsize=(9.6, 5.9))
    draw_bands(ax, profile, 1)
    add_recession_line(ax, profile)
    contour_handles = []
    contour_notes = []
    for threshold in (0.80, 0.90, 0.95):
        depth = contour_depth(profile, threshold)
        threshold_text = localized_number(threshold, 2, language)
        if math.isfinite(depth):
            color = CONTOUR_COLORS[threshold]
            ax.plot(depth, threshold, "o", color=color, markersize=4.5, zorder=6)
            ax.vlines(
                depth,
                0.0,
                threshold,
                colors=color,
                linestyles=":",
                linewidth=0.9,
                zorder=4,
            )
            contour_notes.append(
                text["contour_value"].format(
                    threshold=threshold_text,
                    depth=localized_number(depth, 3, language),
                )
            )
            contour_handles.append(
                Line2D(
                    [0],
                    [0],
                    color=color,
                    linestyle=":",
                    marker="o",
                    markersize=4,
                    label=text["contour"].format(threshold=threshold_text),
                )
            )
        else:
            contour_notes.append(
                text["not_reached"].format(threshold=threshold_text)
            )

    ax.set_xlim(0.0, profile["extent"])
    ax.set_ylim(0.0, 1.045)
    ax.set_xlabel(text["radial_xlabel"])
    ax.set_ylabel(text["ylabel_svar1_radial"])
    if language == "fr":
        ax.xaxis.set_major_formatter(
            FuncFormatter(
                lambda value, _: localized_number(value, 2, language)
            )
        )
        ax.yaxis.set_major_formatter(
            FuncFormatter(
                lambda value, _: localized_number(value, 2, language)
            )
        )
    ax.set_title(
        text["last_title"].format(
            time=localized_number(profile["saved_time"], 4, language),
            recession=localized_number(profile["recession"], 3, language),
        ),
        pad=12,
    )
    add_secondary_axis(ax, profile["extent"], "radial", language)
    ax.text(
        0.985,
        0.06,
        r"\begin{tabular}{r}" + r"\\".join(contour_notes) + r"\end{tabular}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8.5,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.88},
    )
    handles = [
        Patch(
            facecolor=STYLE[1]["fill"],
            edgecolor=STYLE[1]["edge"],
            label=text["sampled"],
        ),
        Patch(
            facecolor="#E4E4E4",
            edgecolor="#666666",
            hatch="////",
            label=text["interpolated"],
        ),
        Line2D(
            [0],
            [0],
            color=RECESSION_COLOR,
            linestyle="--",
            linewidth=1.35,
            label=text["recession"],
        ),
    ] + contour_handles
    ax.legend(
        handles=handles,
        loc="upper right",
        fontsize=8.0,
        frameon=True,
        framealpha=0.92,
        ncol=2,
    )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def main():
    args = parse_args()
    configure_matplotlib()
    history = read_history(args.history_csv)
    if args.contour_only:
        contour_rows = read_contour_distance_csv(DEFAULT_CONTOUR_DISTANCE_CSV)
        for language in ("fr", "en"):
            plot_contour_distances(
                OUTPUTS[("contour_distance", 1, language)],
                contour_rows,
                history,
                language,
            )
        print("Read {}".format(DEFAULT_CONTOUR_DISTANCE_CSV))
        for language in ("fr", "en"):
            print(
                "Wrote {}".format(
                    OUTPUTS[("contour_distance", 1, language)]
                )
            )
        return

    radial_loaded = {
        index: load_profiles(args.radial_csv, "radial", index, history)
        for index in (1, 2)
    }
    axial_loaded = {
        index: load_profiles(args.axial_csv, "axial", index, history)
        for index in (1, 2)
    }
    radial = {index: loaded[0] for index, loaded in radial_loaded.items()}
    radial_latest = {
        index: loaded[1] for index, loaded in radial_loaded.items()
    }
    axial = {index: loaded[0] for index, loaded in axial_loaded.items()}
    contour_profiles = radial[1] + [radial_latest[1]]
    sparse_contour_rows = contour_distance_rows(contour_profiles)
    if DEFAULT_CONTOUR_DISTANCE_CSV.exists():
        contour_rows = read_contour_distance_csv(DEFAULT_CONTOUR_DISTANCE_CSV)
    else:
        contour_rows = sparse_contour_rows
        write_contour_distance_csv(
            DEFAULT_CONTOUR_DISTANCE_CSV,
            contour_rows,
        )

    for language in ("fr", "en"):
        plot_last_radial(
            OUTPUTS[("last_radial", 1, language)],
            radial_latest[1],
            language,
        )
        for axis, profiles_by_svar in (("radial", radial), ("axial", axial)):
            for svar_index in (1, 2):
                plot_temporal(
                    OUTPUTS[(axis, svar_index, language)],
                    profiles_by_svar[svar_index],
                    axis,
                    svar_index,
                    language,
                )
        plot_contour_distances(
            OUTPUTS[("contour_distance", 1, language)],
            contour_rows,
            history,
            language,
        )
    print("Wrote {}".format(DEFAULT_CONTOUR_DISTANCE_CSV))
    for output in OUTPUTS.values():
        print("Wrote {}".format(output))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Plot the maximum SVAR1 value in one-percent radial bands of phe0.

The embedded values were extracted from the last valid distributed ANSYS
result set:

    transient time = 6.3856169387672 s
    phe0 inner radius = 133.350 mm
    phe0 thickness = 2.540 mm

SVAR1 is averaged over all elemental-nodal contributions sharing a global
node ID, matching the smoothed Mechanical representation used for the
reported 0.80, 0.90, and 0.95 contours.

Because the radial mesh has about eight element layers, a few one-percent
bands contain no result node. Those bands are explicitly marked and filled
by linear interpolation between the nearest sampled bands. The generated CSV
retains both the raw and plotted values.

The script produces French and English vector PDFs. All visible text,
including tick labels, is typeset by LaTeX.
"""

import argparse
import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402


ROOT = Path(__file__).resolve().parent
DEFAULT_PDF_FR = ROOT / "svar1_radial_profile_1pct_fr.pdf"
DEFAULT_PDF_EN = ROOT / "svar1_radial_profile_1pct_en.pdf"
DEFAULT_CSV = ROOT / "svar1_radial_profile_1pct.csv"

RESULT_TIME_S = 6.3856169387672
PHE0_INNER_RADIUS_MM = 133.350
PHE0_THICKNESS_MM = 2.540

# Columns: one-percent bin index (zero based), raw nodal maximum, node count.
# "nan" means that no elemental-nodal result location falls in that narrow
# radial band. These entries are interpolated for plotting and kept flagged.
RAW_PROFILE = """
0,1,22814
1,nan,0
2,nan,0
3,nan,0
4,nan,0
5,1,51
6,1,527
7,1,1547
8,1,4879
9,1,7956
10,1,6239
11,1,8585
12,1,9265
13,1,5304
14,0.99999998509883881,1632
15,0.99999998013178504,476
16,0.99999990065892541,765
17,0.99999982118606567,1989
18,0.99999967217445374,2176
19,0.99999928474426270,1717
20,0.99999856948852539,2057
21,0.99999670684337616,3009
22,0.99999395012855530,5644
23,0.99998678763707483,6851
24,0.99997617304325104,7752
25,0.99995943903923035,9265
26,0.99994073311487830,2669
27,0.99988538026809692,1632
28,0.99979502956072486,2074
29,0.99965863426526391,1360
30,0.99946473042170203,629
31,0.99908085167407990,408
32,0.99890361229578650,1241
33,0.99752600789070134,2822
34,0.99671556055545807,4981
35,0.99535566568374634,6171
36,0.99289755821228032,6086
37,0.98925743997097015,6154
38,0.98504814505577087,7973
39,0.98104031383991241,3978
40,0.97327992320060730,629
41,0.96350236237049103,238
42,0.95547936111688614,408
43,0.94275830686092377,459
44,0.93710947036743164,901
45,0.90555666089057918,1666
46,0.88645016402006149,4335
47,0.87592925131320953,7769
48,0.83195235580205917,5304
49,0.80871024131774905,4913
50,0.76531352102756500,7446
51,0.73160398006439209,6664
52,0.70107178092002864,187
53,0.65027090907096863,340
54,0.61167051394780481,408
55,0.63161818186442054,323
56,0.52417433634400368,357
57,0.49554597586393356,850
58,0.50217053294181824,3094
59,0.41205928474664688,7820
60,0.37362473085522652,6341
61,0.33770005777478218,4947
62,0.30277470499277115,6528
63,0.27194529399275780,8381
64,0.24446665868163109,51
65,0.21606027334928513,153
66,0.17693316005170345,51
67,0.15303750522434711,136
68,0.14646076224744320,187
69,0.12880814969539642,170
70,0.15314435586333275,1394
71,0.10039826333522797,4624
72,0.08928185049444437,8840
73,0.07871246384456754,5933
74,0.06678440049290657,7259
75,0.05855735344812274,9214
76,0.04261395288631320,17
77,nan,0
78,nan,0
79,0.02887192275375128,102
80,0.02701489683240652,119
81,0.02146878931671381,68
82,0.02817380484193564,17
83,0.02540502827614546,272
84,0.01555806165561080,595
85,0.01365749456454068,8636
86,0.01192863786127418,15708
87,0.01027846615761519,11900
88,0.00727549509610981,34
89,nan,0
90,nan,0
91,nan,0
92,nan,0
93,nan,0
94,nan,0
95,nan,0
96,nan,0
97,nan,0
98,nan,0
99,0.00207208748906851,18855
"""

# Contours obtained by interpolation of the globally averaged elemental-nodal
# field on element edges at the same result set.
CONTOURS = (
    (0.80, 1.26845203, "#08357E"),
    (0.90, 1.16439859, "#A04A00"),
    (0.95, 1.09800244, "#7A0101"),
)

TEXT = {
    "en": {
        "sampled": r"Sampled 1\% band maximum",
        "interpolated": r"Interpolated band (no result node)",
        "profile": r"Maximum SVAR1 profile",
        "contour": r"SVAR1 $= {threshold}$ contour",
        "annotation": r"SVAR1 $= {threshold}$: ${depth}\,\mathrm{{mm}}$",
        "xlabel": (
            r"Depth through \texttt{phe0} from the hot inner face [\%]"
        ),
        "ylabel": r"Maximum pyrolysis conversion, SVAR1 ($\alpha$)",
        "title": (
            r"Maximum SVAR1 in 1\% radial bands of \texttt{{phe0}}"
            "\n"
            r"Globally averaged elemental-nodal field at "
            r"$t = {time}\,\mathrm{{s}}$"
        ),
        "secondary_xlabel": r"Radial depth from the hot face [$\mathrm{mm}$]",
        "hot_face": r"hot face",
        "outer_face": r"\texttt{phe0} / epoxy",
    },
    "fr": {
        "sampled": r"Maximum par ruban de 1\% échantillonné",
        "interpolated": r"Ruban interpolé (aucun nœud de résultat)",
        "profile": r"Profil du maximum de SVAR1",
        "contour": r"Contour SVAR1 $= {threshold}$",
        "annotation": r"SVAR1 $= {threshold}$ : ${depth}\,\mathrm{{mm}}$",
        "xlabel": (
            r"Profondeur dans \texttt{phe0} depuis la face intérieure chaude [\%]"
        ),
        "ylabel": r"Conversion pyrolytique maximale, SVAR1 ($\alpha$)",
        "title": (
            r"Maximum de SVAR1 par rubans radiaux de 1\% dans \texttt{{phe0}}"
            "\n"
            r"Champ élémentaire-nodal moyenné globalement à "
            r"$t = {time}\,\mathrm{{s}}$"
        ),
        "secondary_xlabel": (
            r"Profondeur radiale depuis la face chaude [$\mathrm{mm}$]"
        ),
        "hot_face": r"face chaude",
        "outer_face": r"\texttt{phe0} / époxy",
    },
}


def configure_matplotlib():
    """Apply the report figure style and use LaTeX for all visible text."""
    mpl_tmp = Path(tempfile.mkdtemp(prefix="mpl_svar1_profile_"))
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_tmp))
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 10.5,
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


def load_profile():
    """Return bin starts, raw maxima, interpolated maxima, and node counts."""
    records = []
    for line in RAW_PROFILE.strip().splitlines():
        index_text, value_text, count_text = line.split(",")
        records.append((int(index_text), float(value_text), int(count_text)))

    indices = np.asarray([row[0] for row in records], dtype=int)
    raw = np.asarray([row[1] for row in records], dtype=float)
    counts = np.asarray([row[2] for row in records], dtype=int)
    if not np.array_equal(indices, np.arange(100)):
        raise RuntimeError("The embedded one-percent profile is incomplete.")

    centers = indices.astype(float) + 0.5
    sampled = np.isfinite(raw)
    plotted = np.interp(centers, centers[sampled], raw[sampled])
    return indices, centers, raw, plotted, counts


def write_csv(path, indices, raw, plotted, counts):
    """Write the numerical profile used by the plot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "bin_index",
                "depth_percent_start",
                "depth_percent_end",
                "depth_mm_start",
                "depth_mm_end",
                "raw_max_svar1",
                "plotted_max_svar1",
                "interpolated",
                "nodal_sample_count",
            )
        )
        for index in indices:
            raw_text = "" if not np.isfinite(raw[index]) else "{:.17g}".format(raw[index])
            writer.writerow(
                (
                    index + 1,
                    index,
                    index + 1,
                    "{:.6f}".format(index * PHE0_THICKNESS_MM / 100.0),
                    "{:.6f}".format((index + 1) * PHE0_THICKNESS_MM / 100.0),
                    raw_text,
                    "{:.17g}".format(plotted[index]),
                    int(not np.isfinite(raw[index])),
                    counts[index],
                )
            )


def localized_number(value, decimals, language):
    """Format a number for use in a localized LaTeX label."""
    text = ("{:.%df}" % decimals).format(value)
    return text.replace(".", ",") if language == "fr" else text


def plot_profile(path, indices, centers, raw, plotted, language):
    """Generate one localized vector PDF figure."""
    if language not in TEXT:
        raise ValueError("Unsupported language: {}".format(language))
    text = TEXT[language]
    sampled = np.isfinite(raw)
    interpolated = ~sampled

    fig, ax = plt.subplots(figsize=(9.6, 5.9))
    ax.bar(
        centers[sampled],
        plotted[sampled],
        width=0.96,
        color="#9CBCE8",
        edgecolor="#315B91",
        linewidth=0.28,
        label=text["sampled"],
        zorder=2,
    )
    ax.bar(
        centers[interpolated],
        plotted[interpolated],
        width=0.96,
        color="#E4E4E4",
        edgecolor="#666666",
        linewidth=0.45,
        hatch="////",
        label=text["interpolated"],
        zorder=2,
    )
    ax.step(
        centers,
        plotted,
        where="mid",
        color="#08357E",
        linewidth=1.45,
        label=text["profile"],
        zorder=3,
    )

    for threshold, depth_mm, color in CONTOURS:
        depth_percent = 100.0 * depth_mm / PHE0_THICKNESS_MM
        ax.hlines(
            threshold,
            0.0,
            depth_percent,
            colors=color,
            linestyles="--",
            linewidth=1.0,
            alpha=0.86,
            zorder=4,
        )
        ax.vlines(
            depth_percent,
            0.0,
            threshold,
            colors=color,
            linestyles=":",
            linewidth=0.95,
            alpha=0.86,
            zorder=4,
        )
        ax.plot(depth_percent, threshold, "o", color=color, markersize=4.5, zorder=5)
        threshold_text = localized_number(threshold, 2, language)
        depth_text = localized_number(depth_mm, 3, language)
        ax.annotate(
            text["annotation"].format(
                threshold=threshold_text,
                depth=depth_text,
            ),
            xy=(depth_percent, threshold),
            xytext=(depth_percent + 2.0, threshold + 0.016),
            fontsize=8.6,
            color=color,
            ha="left",
            va="bottom",
        )

    ax.set_xlim(0.0, 100.0)
    ax.set_ylim(0.0, 1.045)
    ax.set_xticks(np.arange(0.0, 101.0, 10.0))
    ax.set_yticks(np.arange(0.0, 1.01, 0.1))
    if language == "fr":
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda value, _: localized_number(value, 1, language))
        )
    ax.set_xlabel(text["xlabel"])
    ax.set_ylabel(text["ylabel"])
    ax.set_title(
        text["title"].format(
            time=localized_number(RESULT_TIME_S, 4, language),
        ),
        fontsize=12,
        pad=10,
    )

    def percent_to_mm(percent):
        return np.asarray(percent) * PHE0_THICKNESS_MM / 100.0

    def mm_to_percent(depth_mm):
        return np.asarray(depth_mm) * 100.0 / PHE0_THICKNESS_MM

    secondary = ax.secondary_xaxis(
        "top",
        functions=(percent_to_mm, mm_to_percent),
    )
    secondary.set_xlabel(text["secondary_xlabel"], labelpad=7)
    secondary.set_xticks(np.linspace(0.0, PHE0_THICKNESS_MM, 6))
    secondary.xaxis.set_major_formatter(
        FuncFormatter(lambda value, _: localized_number(value, 3, language))
    )

    ax.text(
        0.5,
        0.025,
        text["hot_face"],
        transform=ax.get_xaxis_transform(),
        ha="left",
        va="bottom",
        fontsize=8.5,
        color="#444444",
    )
    ax.text(
        99.5,
        0.025,
        text["outer_face"],
        transform=ax.get_xaxis_transform(),
        ha="right",
        va="bottom",
        fontsize=8.5,
        color="#444444",
    )

    contour_handles = [
        plt.Line2D(
            [0],
            [0],
            color=color,
            linestyle="--",
            marker="o",
            markersize=4,
            linewidth=1.0,
            label=text["contour"].format(
                threshold=localized_number(threshold, 2, language),
            ),
        )
        for threshold, _, color in CONTOURS
    ]
    handles, labels = ax.get_legend_handles_labels()
    handles.extend(contour_handles)
    labels.extend(handle.get_label() for handle in contour_handles)
    ax.legend(
        handles,
        labels,
        loc="lower left",
        frameon=True,
        framealpha=0.95,
        fontsize=8.3,
        ncol=2,
    )

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, backend="pgf", bbox_inches="tight")
    plt.close(fig)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-fr", type=Path, default=DEFAULT_PDF_FR)
    parser.add_argument("--pdf-en", type=Path, default=DEFAULT_PDF_EN)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--language",
        choices=tuple(TEXT),
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Matplotlib's LaTeX/PDF backend can corrupt filled paths when two TeX-heavy
    # figures are saved successively in the same process. Each localized figure
    # is therefore rendered in a fresh Python process.
    if args.language:
        configure_matplotlib()
        indices, centers, raw, plotted, _ = load_profile()
        target = args.pdf_fr if args.language == "fr" else args.pdf_en
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".svar1_pdf_",
            dir=target.parent,
        ) as temporary:
            temporary_pdf = Path(temporary) / target.name
            plot_profile(
                temporary_pdf,
                indices,
                centers,
                raw,
                plotted,
                args.language,
            )
            os.replace(temporary_pdf, target)
        print("wrote {}".format(target))
        return

    indices, _, raw, plotted, counts = load_profile()
    write_csv(args.csv, indices, raw, plotted, counts)

    common_arguments = (
        "--pdf-fr",
        str(args.pdf_fr),
        "--pdf-en",
        str(args.pdf_en),
        "--csv",
        str(args.csv),
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

    print("wrote {}".format(args.csv))


if __name__ == "__main__":
    main()

"""Shared LaTeX/serif typography for every documentation figure.

Requires a working LaTeX installation and the fontenc, inputenc, lmodern,
and siunitx packages. Do not silently fall back to Matplotlib fonts.
"""
import matplotlib as mpl
from cycler import cycler
import math


def plot_samples(ax, x, y, *, highlight_latest=True, **kwargs):
    """Use the earlier simulation3 recession plot's circular sample styling.

    Retain every sample in the line. Display up to about 80 sample markers
    plus the final sample to avoid a solid band on dense 405-step histories.
    Markers always coincide with existing samples, never interpolated points.
    """
    stride = max(1, math.ceil(len(x) / 80))
    marked = sorted(set(range(0, len(x), stride)) | {len(x) - 1})
    line, = ax.plot(x, y, marker="o", markersize=2.8, linewidth=1.55,
                    markevery=marked, **kwargs)
    if highlight_latest:
        ax.scatter([x[-1]], [y[-1]], marker="o", color="#A04A00",
                   s=31, zorder=3, label="_nolegend_")
    return line


def configure_latex():
    # Match the earlier phenolic_case_study/tmp3 documentation: LaTeX serif,
    # white background, boxed axes, light grey grid and the report palette.
    mpl.rcParams.update({
        "text.usetex": True,
        "font.family": "serif",
        "font.serif": ["Computer Modern Roman"],
        "font.size": 9.5,
        "axes.unicode_minus": False,
        "axes.edgecolor": "#333333",
        "axes.labelcolor": "#111111",
        "xtick.color": "#111111",
        "ytick.color": "#111111",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "axes.spines.top": True,
        "axes.spines.right": True,
        "axes.grid": True,
        "grid.alpha": .24,
        "grid.color": "#7f7f7f",
        "grid.linewidth": .5,
        "axes.axisbelow": True,
        "axes.prop_cycle": cycler(color=["#08357E", "#A04A00", "#38761D", "#A64D79"]),
        "lines.linewidth": 1.55,
        "pdf.fonttype": 42,
        "text.latex.preamble": (
            r"\usepackage[T1]{fontenc}"
            r"\usepackage[utf8]{inputenc}"
            r"\usepackage{lmodern}"
            r"\usepackage{siunitx}"
        ),
    })

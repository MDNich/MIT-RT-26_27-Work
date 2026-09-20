#!/usr/bin/env python3
"""Create bilingual planning figures for the new-motor v0 reports."""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

mpl.rcParams.update(
    {
        "text.usetex": True,
        "font.family": "serif",
        "font.serif": ["Computer Modern Roman"],
        "axes.unicode_minus": False,
        "text.latex.preamble": (
            r"\usepackage[T1]{fontenc}"
            r"\usepackage[utf8]{inputenc}"
            r"\usepackage{lmodern}"
            r"\usepackage{siunitx}"
        ),
    }
)

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Patch, Rectangle


ROOT = Path(__file__).resolve().parent
PHENOLIC = "#A65A2E"
ALUMINIUM = "#A8B0B8"
GAS = "#F6D7C9"
INK = "#20242A"


def geometry(lang: str) -> None:
    fr = lang == "fr"
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    radii = (66.675, 71.4375, 76.2)
    ax.add_patch(Circle((0, 0), radii[2], facecolor=ALUMINIUM, edgecolor=INK, lw=1.2))
    ax.add_patch(Circle((0, 0), radii[1], facecolor=PHENOLIC, edgecolor=INK, lw=1.2))
    ax.add_patch(Circle((0, 0), radii[0], facecolor=GAS, edgecolor=INK, lw=1.2))
    ax.plot([16, radii[2]], [0, 0], color=INK, lw=.8)
    labels = [
        (radii[0], r"ID ph\'enolique $5{,}250\,\mathrm{in}$ / $133{,}350\,\mathrm{mm}$" if fr else r"Phenolic ID $5.250\,\mathrm{in}$ / $133.350\,\mathrm{mm}$"),
        (radii[1], r"OD ph\'enolique = ID aluminium $5{,}625\,\mathrm{in}$ / $142{,}875\,\mathrm{mm}$" if fr else r"Phenolic OD = aluminium ID $5.625\,\mathrm{in}$ / $142.875\,\mathrm{mm}$"),
        (radii[2], r"OD aluminium $6{,}000\,\mathrm{in}$ / $152{,}400\,\mathrm{mm}$" if fr else r"Aluminium OD $6.000\,\mathrm{in}$ / $152.400\,\mathrm{mm}$"),
    ]
    offsets = (27, 11, -8)
    for (radius, text), y in zip(labels, offsets):
        ax.annotate(text, xy=(radius, 0), xytext=(86, y), textcoords="data",
                    arrowprops=dict(arrowstyle="->", color=INK, lw=.8), ha="left", va="center", fontsize=9)
    ax.text(0, 0, r"Gaz / al\'esage" if fr else "Gas / bore", ha="center", va="center", fontsize=10)
    ax.legend(handles=[
        Patch(facecolor=PHENOLIC, edgecolor=INK, label=r"Ph\'enolique -- $4{,}7625\,\mathrm{mm}$" if fr else r"Phenolic -- $4.7625\,\mathrm{mm}$"),
        Patch(facecolor=ALUMINIUM, edgecolor=INK, label=r"Aluminium -- $4{,}7625\,\mathrm{mm}$" if fr else r"Aluminium -- $4.7625\,\mathrm{mm}$"),
    ], loc="lower right", frameon=True, fontsize=9)
    ax.set_title(r"Nouvelle g\'eom\'etrie nominale -- coupe radiale" if fr else "New nominal geometry -- radial cross-section", weight="bold")
    ax.set_aspect("equal")
    ax.set_xlim(-82, 166)
    ax.set_ylim(-83, 83)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(ROOT / f"newmotor_geometry_{lang}.pdf", bbox_inches="tight")
    plt.close(fig)


def mesh(lang: str) -> None:
    fr = lang == "fr"
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(8.0, 4.5), gridspec_kw={"width_ratios": [1.1, 1.35]})
    ax.add_patch(Rectangle((0, 0), 4.7625, 1, facecolor=PHENOLIC, edgecolor=INK))
    ax.add_patch(Rectangle((4.7625, 0), 4.7625, 1, facecolor=ALUMINIUM, edgecolor=INK))
    for i in range(0, 241, 12):
        x = i * 4.7625 / 240
        ax.plot([x, x], [0, 1], color="white", lw=.25, alpha=.8)
    for i in range(0, 65, 4):
        x = 4.7625 + i * 4.7625 / 64
        ax.plot([x, x], [0, 1], color="white", lw=.35, alpha=.8)
    ax.text(2.38125, .5, (r"240 rang\'ees" + "\n" + r"$19{,}84375\,\mu\mathrm{m}$") if fr else ("240 rows\n" + r"$19.84375\,\mu\mathrm{m}$"),
            ha="center", va="center", color="white", weight="bold")
    ax.text(7.14375, .5, (r"64 rang\'ees" + "\n" + r"$74{,}414\,\mu\mathrm{m}$") if fr else ("64 rows\n" + r"$74.414\,\mu\mathrm{m}$"),
            ha="center", va="center", color=INK, weight="bold")
    ax.set_xlim(0, 9.525)
    ax.set_ylim(-.15, 1.15)
    ax.set_xlabel(r"\'Epaisseur radiale depuis l'al\'esage $[\mathrm{mm}]$" if fr else r"Radial depth from bore $[\mathrm{mm}]$")
    ax.set_yticks([])
    ax.set_title(r"Discr\'etisation radiale" if fr else "Radial discretization", weight="bold")

    data = [
        ("Angle", r"$0{,}10^{\circ}$" if fr else r"$0.10^{\circ}$"),
        ("Axial", r"$250 \times 0{,}20\,\mathrm{mm}$" if fr else r"$250 \times 0.20\,\mathrm{mm}$"),
        (r"Circonf\'erentiel" if fr else "Circumferential", "2 divisions"),
        (r"N\oe uds" if fr else "Nodes", r"$229\,665$"),
        (r"Hexa\`edres" if fr else "Hexahedra", r"$152\,000$"),
        (r"Faces par rang\'ee" if fr else "Faces per row", "500"),
        (r"\'Echelle anneau complet" if fr else "Full-ring scale", r"$\times\,3\,600$"),
    ]
    ax2.axis("off")
    table = ax2.table(cellText=data, colLabels=[r"Param\`etre" if fr else "Parameter", "Valeur" if fr else "Value"],
                      loc="center", cellLoc="left", colLoc="left")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.6)
    for (row, _), cell in table.get_celld().items():
        cell.set_edgecolor("#D0D4D8")
        if row == 0:
            cell.set_facecolor("#E8EDF2")
            cell.set_text_props(weight="bold")
    ax2.set_title("Inventaire du maillage" if fr else "Mesh inventory", weight="bold", pad=12)
    fig.suptitle(r"Maillage structur\'e conforme valid\'e sous MAPDL" if fr else "Conformal structured mesh validated in MAPDL", weight="bold")
    fig.tight_layout()
    fig.savefig(ROOT / f"newmotor_mesh_{lang}.pdf", bbox_inches="tight")
    plt.close(fig)


for language in ("fr", "en"):
    geometry(language)
    mesh(language)

"""Typeset revision 2 report graphics with the report's pdfLaTeX and Latin Modern fonts."""
import matplotlib

matplotlib.use("pgf")
matplotlib.rcParams.update({
    "pgf.texsystem": "pdflatex",
    "pgf.rcfonts": False,
    "pgf.preamble": r"\usepackage[T1]{fontenc}\usepackage{lmodern,amsmath,textcomp}",
    "font.family": "serif",
    "text.usetex": True,
})

from matplotlib import pyplot as plt

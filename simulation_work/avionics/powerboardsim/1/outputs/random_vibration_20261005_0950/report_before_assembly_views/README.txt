POWER BOARD RANDOM VIBRATION - 5 OCTOBER 2026

The report contains separate X, Y and Z base-excitation cases for the model
with six locked bolts preloaded to 750 N each and 2% assumed modal damping.
These are exploratory linear elastic results, not a qualified strength or
fatigue assessment. See the report's model and qualification sections.

Files
- power_board_random_vibration.tex: editable LaTeX report.
- figures/: ordinary external PDF and PNG graphics referenced by includegraphics.
- power_board_random_vibration.pdf: compiled and visually checked report.
- power_board_random_vibration_results.csv: 51 result-object summaries; numeric
  values retain the explicit native units in the unit column.
- modal_frequencies.csv: 38 prestressed frequencies used by the PSD analyses.
- stress_hotspot_bodies.tsv: native nodal/elemental maxima mapped to CAD bodies.
- study_config.json: original study specification and initial source identifiers.
  The expanded modal analysis actually used is 4254; PSD analyses are 4259,
  4264 and 4269. See verification_summary.json for final accepted identities.

Compile from this folder with an installed TeX distribution, or upload this
folder including figures/ to a LaTeX project editor:
    pdflatex power_board_random_vibration.tex
    pdflatex power_board_random_vibration.tex
No shell escape, raster payload, or generated image byte data is in the source.
The Codex built-in standalone preview does not currently resolve this external
figure folder. The supplied PDF was successfully built with pdfLaTeX.

The preserved native solver evidence is in the source project directory:
outputs/random_vibration_20261005_0950/
The three Mechanical analyses are solved and reference the accepted archived
result files there. Keep that directory with the Workbench project.

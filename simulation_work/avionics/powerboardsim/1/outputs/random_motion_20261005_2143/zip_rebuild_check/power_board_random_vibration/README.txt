POWER BOARD RANDOM VIBRATION - 5 OCTOBER 2026

The report contains separate X, Y and Z base-excitation cases for the model
with six locked bolts preloaded to 750 N each and 2% assumed modal damping.
These are exploratory linear elastic results, not a qualified strength or
fatigue assessment. See the report's model and qualification sections.

Files
- power_board_random_vibration.tex: editable LaTeX report.
- figures/: seventeen external ANSYS PNG contours referenced by includegraphics.
- plots/: editable native PGFPlots/TikZ code for both graphs.
- data/: ordinary CSV data read by the modal effective-mass LaTeX plot.
- assembly_body_response_audit.csv: body inventory and per-case response coverage.
- assembly_scope_audit.json: all 208 meshed bodies, including 172 ECAD bodies,
  have finite response values in all three cases.
- power_board_random_vibration.pdf: compiled and visually checked report.
- power_board_random_vibration_results.csv: 51 result-object summaries; numeric
  values retain the explicit native units in the unit column.
- modal_frequencies.csv: 38 prestressed frequencies used by the PSD analyses.
- stress_hotspot_bodies.tsv: native nodal/elemental maxima mapped to CAD bodies.
- study_config.json: original study specification and initial source identifiers.
  The expanded modal analysis actually used is 4254; PSD analyses are 4259,
  4264 and 4269. See verification_summary.json for final accepted identities.

Compile from this folder with an installed TeX distribution, or upload this
folder including figures/, plots/ and data/ to a LaTeX project editor:
    pdflatex power_board_random_vibration.tex
    pdflatex power_board_random_vibration.tex
Both graphs are native LaTeX plots, not included raster or PDF graphics.
No shell escape, raster payload, or generated image byte data is in the source.
The Codex built-in standalone preview does not currently resolve this external
asset folders. The supplied PDF was successfully built with pdfLaTeX.

The preserved native solver evidence is in the source project directory:
outputs/random_vibration_20261005_0950/
The three Mechanical analyses are solved and reference the accepted archived
result files there. Keep that directory with the Workbench project.

REPRODUCTION APPENDIX REVISION
The report now includes a numbered, detailed reproduction procedure.
reproduction/ contains native inputs, original reference scripts, scopes,
audits and a SHA-256 manifest. No numerical results were changed.
Compile the delivered TeX directly; old builders predate the appendix.
Nine added battery-side oblique views show every directional displacement
component for each excitation case. These are fresh native ANSYS exports.

ENGLISH FIGURE REVISION
All report Mechanical images were re-exported in English, including the
Workbench study headings. Numerical results are unchanged. Translation
and export scripts and their audits are bundled. The original result
archives remain intact. The straight Back view includes a 1.25 fit margin.

MOTION VIDEO SUPPLEMENT - 6 OCTOBER 2026
Sections 19-23 reproduce the separate seeded X/Y/Z time-history calculations,
transient expansion, native 4K/60 fps exports, and dynamic stress recovery.
The numerical input/field checks are in reproduction/motion/. The companion
videos are separate files in output/videos/power_board_random_motion_4k60/.
The older camera-only RMS clips remain clearly labelled in the other gallery.
The Python Result display requires the documented graphics-scale correction,
which was checked against built-in Mechanical results without changing the
reported numerical fields. Static clamp stress is excluded from the dynamic
stress movie. The original RMS report results remain unchanged.

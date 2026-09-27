# Extended OR / RASAero coefficient atlas

Start with `index.html` for a searchable local gallery. The full report is the parent's parent `mit-or-rasaero-study.tex` and `output/pdf/mit-or-rasaero-study.pdf`, following the team's solid-propellant report style. This extension contains **92 configurations, 82,800 matched Mach/angle points, 42 figure sheets and 176 panels**.

## What was run

67 new native RASAero configurations supplement the original 25. All new RASAero coefficients were generated in the Windows 11 VM through the Aero Plots GUI and exported as CSV. All 92 cases were evaluated using the installed MIT OpenRocket JAR through its public aerodynamic API at Mach 0.01–3.00 in steps of 0.01, and at angles of attack 0, 2 and 4 degrees. There are 24 additional native OR roughness sweeps used only to verify the matched-roughness reconstruction. No OR source or installed binary was modified.

The matrix covers nose shape/fineness, fin thickness/bevel/sweep/span/taper/profile, geometric scaling and body length, surface roughness, turbulent versus transitional flow, nozzle-area sensitivity, and default versus Rogers Modified Barrowman normal-force/CP predictions. `cases.json` is the complete input manifest. `new-cases.txt` identifies the 67 new configurations; `remaining-cases.txt` documents the resumed portion after RASAero exited once. The independent Hsq restart repeat is identical in every exported column to the original baseline (see `evidence/final-integrity.json`).

## Coefficient definitions

All coefficients use body frontal area. CA and CN are body-axis axial and normal force coefficients. CD and CL are wind-axis drag and lift:

- CD = CA cos(alpha) + CN sin(alpha)
- CL = CN cos(alpha) - CA sin(alpha)

At nonzero angle, the native OR stored `cd0` is not the comparable wind-axis CD. The table uses the transform above. Raw RASAero exports concatenate the three angles; **filter Alpha before interpolation**, since Mach is not globally sorted. Raw RASAero CL follows the power-on convention when nozzle area is nonzero. The main comparison reconstructs coast lift from CA Power-Off and CN. All force-axis identities are checked in `axis-audit.csv`.

CP is a location from the nose tip, not a stability margin. The table stores meters; plots display body diameters. The plotted normal-force slope is the same 0-to-4-degree secant in both programs. Supersonic OR normal-force/CP outputs are shown with the engine's known body-model limitation above Mach 1.1.

## Physical roughness

RAS values are 1.27, 6.35, 30.48 and 152.4 micrometers. The nearest native OR values used in the input/engine comparison are 2, 5, 20 and 150 micrometers; these gray curves are explicitly not a physical match. Exact-roughness curves are separately reconstructed using the unmodified OR friction correlation, preserving pressure and base terms. This reconstruction agrees with all 24 direct native-finish checks within 1.5e-12 in Cd. The common-state table contains both native OR values and `or_cd0_exact_ras_roughness` / `or_cd_wind_exact_ras_roughness`.

The reconstruction is not installed code, an independently validated new aerodynamic model, or a fit to RASAero. The data show that physical roughness matching still leaves different responses.

## Files

- `models/`: the 92 native CDX1 configurations actually used as inputs.
- `rasaero/`: 92 raw GUI exports; the extra restart repeat is under `evidence/`.
- `openrocket/`: 116 installed-engine result files (92 cases plus 24 finish verification sweeps).
- `matched-coefficients.csv`: 82,800 common Mach/angle rows, including physical roughness values and consistently defined coefficients.
- `error-metrics.csv`: absolute, signed, RMS and maximum deviations in subsonic (0.10–0.80), transonic (0.81–1.30), and supersonic (1.31–3.00) bands. Native roughness comparisons are confounded where values differ; use the exact-roughness columns for matched-k analysis.
- `axis-audit.csv`: force-coordinate identity checks for all configurations and angles.
- `analysis-summary.json`: selected numerical findings and native roughness verification errors.
- `figure-data.json`: full arrays behind the atlas; numerical metrics use all points.
- `figures/`: 42 SVG vector figures and 42 PNG previews.
- `index.html`: local gallery with search and topic filters, no external services.
- `evidence/`: UI screenshots/logs, restart repeat, and preservation checks.
- `scripts/`: independent study helpers, not OR application code.

## Reproduction

The saved native inputs are authoritative. `create_cases.py` copies and varies the preserved 25-case models. `CoefficientSweep.java` reads those dimensions and uses the installed MIT JAR; compile/run with Java 17 and the JAR on the classpath. It checks each drag component sum. It does not run flight trajectories. `run_aero_ui.py` automates native Windows controls; process IDs/window state and paths are session-specific, and output overwrite dialogs require care. Preserve existing results and choose a fresh output directory before rerunning the UI.

After raw results exist, run `analyze_extended.py`, `plot_atlas.py`, and `gallery.py`. The parent study's `scripts/build_latex_report.py` embeds the atlas into the same standalone `.tex` file, with no external figure dependencies. These commands regenerate their own outputs; preserve manual edits before using them.

## Interpretation

RASAero is a comparison target, not measured aerodynamic truth. The square-fin roughness and thin-fin limits are retained as model-behavior diagnostics. Nozzle-area plots identify a dependency absent from this OR model; they do not infer an absolute base-pressure coefficient. Original flight results, the first 25-case data, and the installed OR engine are preserved. No new flight performance is claimed from these coefficient-only sweeps.

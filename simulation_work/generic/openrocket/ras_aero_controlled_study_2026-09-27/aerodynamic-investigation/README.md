# Aerodynamic investigation, 27 September 2026

Read the aerodynamic investigation in the parent `mit-or-rasaero-study.tex` / `output/pdf/mit-or-rasaero-study.pdf`. No MIT OpenRocket source or installed binary was changed.

## Contents

- `cases.json`: 25 explicit geometry/nozzle variations, based on the original matched exports.
- `models/*.CDX1`: actual native inputs loaded in RASAero II in the Windows 11 VM.
- `rasaero/*.csv`: unaltered GUI Aero Plots exports. Each concatenates Alpha = 0, 2 and 4 degrees. Filter Alpha = 0 **before** interpolation; the Mach column is not globally monotonic.
- `openrocket/*.csv`: installed MIT engine sweeps on the same external dimensions, with component sums validated.
- `matched-coefficients.csv`: 7,500 common points, Mach 0.01–3.00. Nozzle probes have deliberately unchanged OR curves because this OR fixture has no nozzle correction.
- `analysis-results.json`: extraction audit, Reynolds sensitivity, selected differences, and the unfitted nose-term trial.
- `figures/`: exportable scientific figures (PDF and PNG). Plot data are also embedded in the standalone report source.
- `evidence/`: Windows GUI screenshots and logs, primary-document extracts, and before/after OR fingerprints. The Sbev baseline was exported before this batch and is physically identical to the retained Sbev fixture.
- `scripts/`: fixture generation, GUI orchestration, installed-engine calls, and offline analysis. These are isolated research helpers, not OR application changes.

## Reproduction

Use the same MIT JAR hash recorded in the evidence. The saved CDX1 inputs are authoritative. Compile and run `scripts/AeroSweep.java` with Java 17 and the installed MIT JAR on the classpath. It writes its own `openrocket/` results. The fixture sets sea-level ISA, zero angle/rates, mirror finish (zero roughness), fully turbulent flow, and reads all external dimensions from the native RAS input. No flight trajectory is simulated in this sweep.

In the Windows VM, open each input in RASAero, open Aero Plots, and use File > Export > CSV. The helper `scripts/run_aero_ui.py` automates that workflow; its process ID, current window state and native helper installation are session-specific. It assumes output filenames do not already exist, so preserve existing outputs and use a fresh directory when rerunning. `scripts/windows-ui` retains the native helper provenance. The original GUI batch used the identical helper at `/tmp/rasaero-comparison/ui.py`.

Once exports exist, run `python3 scripts/analyze_aerodynamics.py` from this directory or any directory. It filters Alpha=0, verifies strictly increasing Mach, interpolates only onto exact OR Mach points, calculates error metrics, and regenerates the figures. The nose proposal is an independent algebraic post-processing substitution on Mach 1.32–3, without fitted RAS constants. It does not modify OR or establish new flight performance.

The parent `scripts/build_latex_report.py` embeds `scripts/aero_report.py` into the one standalone `.tex` file; external figures are not needed to compile it. Manual edits to the generated report source should be preserved before regeneration.

## Interpretation limits

The finless/finned subtraction measures a **net fin addition**, including any interference/exposed-area effects, not a RASAero internal pressure term. A full-diameter-nozzle power-off/on difference is a sensitivity observable, not a proven absolute base coefficient. The very thin square-fin result is flagged as a questionable limiting behavior and is not recommended as a calibration target. The mean aerodynamic chord friction trial is too small to explain the main fin gap. No universal Cd multiplier is recommended. RASAero agreement is not validation against measurements.

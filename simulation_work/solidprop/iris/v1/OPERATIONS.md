# Unattended continuation

Read the parent AGENTS.md first. The user authorized the complete exploratory
study, English reports and milestone pushes, and is away from the computer.
Do not ask for repeated approval. Earlier studies must remain unchanged.

## First actions on every continuation

1. Run `model/ops.py check`. Stop all work on a real storage threshold or
   latched storage stop. Mac floor 400 GB decimal; Windows C: floor 10 GB.
2. Inspect `ansystmp/host_storage_status.json`, `storage_guard.pid`,
   `baseline_queue.pid`, `baseline_queue.log`, and `active_runs.json`.
   Check the PID's actual command before signalling it. `caffeinate -i` follows
   the storage watcher PID to prevent idle system sleep; the display may sleep.
   Reattach it if the watcher is restarted, and release it when the study ends. Never start a second
   queue or solver while one is active. Do not kill license services.
3. The intended serial queue is `configs/campaign_queue.json`. Native runs
   are in `ansystmp/runs`. Some execute in `C:\IrisStudy\runs` and mirror
   accepted audit/state files to the Mac. Complete native outputs are copied
   back at process exit. Never delete guest files without verified copies.
4. Native phase exit files must be successful, and `model/validate_run.py`
   must pass all accepted steps and input hashes. The queue applies this
   validation before advancing. Native elapsed/CPU performance warnings and
   the known USERCK warning are recorded, not hidden.

## State at the sustainer and sensitivity milestone

All four 0.1 s pilots passed. Four native analytical steady-conduction
benchmarks passed within 0.013 K. Storage-fault and pulse-boundary logic tests
passed. A guest-local pilot exactly reproduced the shared-drive pilot.

The sustainer Al and CF 20-row baselines completed 7 s, 560 accepted steps each, no row
removal, maximum step energy error 0.6837%, and no failed mass or hot-power
checks. Its controlled pause at 1 s and resume matched an uninterrupted
native reference at 1.1 s exactly in nodal temperature and conversion;
`validation/restart_comparison.json` records the comparison. The native pulse
control also passed all five cooling steps; the remaining queue contains the
two booster coarse baselines and four refined
seven-second pulse/cooling cases. Refined native meshes use 80 phenolic and
20 casing rows; the short sector still has only 2 axial and 2 angular cells.

`model/compare_controls.py` can be rerun after the native pulse control exits.
It verifies the five prescribed cooling steps and writes a compact record.
If the queue observer needs recovery, first inspect active processes and exit
files. `run_queue.py --wait-resume-first` observes the already explicitly
resumed first runtime; existing launch records prevent duplicate phase
launches. An unexplained failure is not blindly retried.

The queue now runs `topology_benchmark.py` before the booster Al baseline unless
its accepted verification record already exists. All 16 constant-property
states passed: first-row removal, only the last phenolic row remaining, and
all phenolic removed, for all four cases. Maximum analytical temperature error
was 0.000471 K. The first static fixture omitted NROPT,FULL; preserve its ignored
failed runtime. Production transient inputs already had that option. Eight
known static load-factor/dead-element table warnings remain documented.
`check_final_event.py` also passed the manufactured final controller event;
neither test is a physical burnthrough result.

The booster Al run launch initially encountered a Parallels InvalidArgument
communication failure. Read-only process and guest-artifact checks established
that it had not launched; one explicit reissue then started successfully.
`validation/booster_al_launch_recovery.json` records this. Do not infer that a
future communication failure authorizes blind launch retries.

`compare_radial_native.py` now compares complete native radial profiles at
0.1, 1, 2, 5 and 7 s. Both sustainer checks passed, maximum difference 1.016 K
and conversion difference 0.00264. Rerun after the booster baselines complete.

## Numerical findings that must remain explicit

Independent data in `validation/radial/` are not ANSYS results. The radial
assembly uses diagonal heat capacity to match SOLID278 without advection.
The prior radial script used a consistent matrix and must not be copied as an
exact transient reference. Short-time sustainer hot-face differences are about
0.70 K at 0.1 s and 0.97 K at 1 s.

Twenty phenolic rows do not resolve recession. Seven-second 20/40/80/160-row
checks and finer time steps are recorded. The geometric retained thickness is
not a measurement of physical liner thickness. Consumed char remains in a
live FE cell until whole-row removal; this approximation and lagged coupling
need independent numerical assessment.

Files named `*_endurance_*` contain REJECTED numerical stress tests: casing
properties had left scope and apparent exhaustion times were mesh/time-step
dependent. Never present these as motor burnthrough predictions. Physically
interpreted long cases stop at the provisional property-range flag: 150 C CF,
300 C Al. These thresholds are not certified structural failure temperatures.

`refine_radial_limits.py` has completed; the compact comparison is
`validation/property_limit_convergence.json`. Inspect
`ansystmp/radial_refined_limits.pid` and its log before launching anything.
It compares 80/.003125, 160/.0015625 and 320/.00078125 (rows/seconds). The
initial smaller-step results substantially reduce the long-time sensitivity:
sustainer Al reaches its model-range flag near 49.6 s with about 3.04 mm
retained, rather than the misleading coarse-time values. These are still
independent exploratory results, not native or measured lifetimes.

Pulse/cooling and heat-load/radiation/removal-cost screenings are already in
`validation/radial/`; their logs are `radial_pulse.log` and
`radial_sensitivity.log`. Coarse-time sensitivity outputs must be treated as
screening until time accuracy is assessed. Heat soak matters: the independent
sustainer CF seven-second pulse crosses the provisional 150 C flag after the
heating ends. Validate refined native cooling histories before a final claim.

## Remaining work

The 54 `*_fine_*.json` independent sensitivity cases are complete (80 radial
cells per material, 0.003125 s ceiling), all stopped at their provisional
property flag with no exhaustion event. They vary heating, hot radiation,
removal cost, phenolic conductivity/capacity, pressure, and supported CF
surrogates. Maximum assembled energy/mass residuals are below 5.4e-11/1e-15.
These are numerical balances, not physical calibration. Small percent-level
changes may still be comparable to discretization error. Parameter-support
changes reproduce the previous default solution exactly; running native
packages remain sealed with their original source hashes.

`refine_input_sensitivities.py` is checking ten strongest/alternative-input
scenarios at 160 rows and a 0.0015625 s ceiling. Inspect its ignored PID/log
`input_sensitivity_refinement` before restarting anything. The compact
`validation/input_sensitivity_refinement.json` includes `complete` and per-case
five-percent timing checks. Report only completed comparisons; it does not
individually refine every small pressure or CF-conductivity perturbation.

- Finish and inspect the native queue; fix any failed audits rather than
  accepting interrupted states. Compare native refined data with the radial
  model, including first-row removal and applied hot-face load transfer.
- Keep manufactured last-row/final-event verification distinct from physical
  recession; do not force a lifetime by extrapolating invalid properties.
- Complete spatial/time comparisons and quantify retained partial-cell
  storage. Inspect refined radial limit results before choosing further cases.
- Check numerical resolution of the strongest input sensitivities, keeping
  engineering perturbations distinct from measured ranges.
- Report temperatures during cooling, remaining mass and geometric thickness,
  pyrolysis depth, uncertainty, and clear valid-exposure bounds for each case.
  A finite burnthrough prediction is not required if it cannot be defended.
- Finish the English report with an executive summary, setup, physics, solver,
  validation, four-case results, graphs and limitations. Remove stale future
  tense when a check completes. A scientific inability to infer actual motor
  lifetime must be explained; never substitute a rejected diagnostic time.

## Reporting and publication

Use the ignored environment `ansystmp/venv/bin/python` to run
`docs/analysis/make_report.py`. It freezes accepted native histories only.
The output is `output/pdf/iris_phenolic_report.pdf`; current report has ten
pages. Render with pdftoppm and visually inspect changed pages before every
published edition, following the PDF skill. The PDF creation marker already
ran successfully once for this conversation; do not repeat it unnecessarily.

The report generator and `report_supplement.py` now include native casing
curves, mass bookkeeping, profile comparisons, property-scope limits and fine
sensitivity figures. Extend these for completed booster and refined cooling
histories; update the executive summary and next-results prose as the campaign
advances. It reads restart/pulse/topology records to avoid stale verification
claims. Keep rejected diagnostics separate from accepted native plots and
actual motor claims. This edition's ten rendered pages were visually checked;
the native snapshot was frozen before the booster Al run began.

Run `model/publish.py '<milestone message>' --push` only after checks and PDF
visual review. It stages Iris-only changes and rejects any file/new Git blob
at or above 100,000,000 bytes. Native results, environments and scratch are
ignored. Push each meaningful setup/report/results milestone.

A 30-minute in-chat heartbeat named "Iris ANSYS study and English reports"
continues this task. Keep it active while substantive work remains. Stop it
on final completion or a real storage stop. Do not send unchanged status
updates. No sub-agent delegation is authorized.

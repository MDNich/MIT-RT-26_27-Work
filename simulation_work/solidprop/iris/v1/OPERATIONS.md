# Unattended continuation

Read the parent AGENTS.md and phenolic_burnthrough_plan.md. The user authorized
this exploratory four-case study, English reports and milestone pushes, and is
away. Do not seek repeated approval. Do not alter earlier studies. No sub-agent
delegation is authorized.

## First actions on every continuation

1. Run `model/ops.py check`. Stop all work on a real or latched storage stop.
   Mac floor: 400,000,000,000 bytes; Windows C: floor: 10,000,000,000 bytes.
   A storage stop prohibits automatic resume. Stop this heartbeat too.
2. Read ignored `ansystmp/host_storage_status.json`, `storage_guard.pid`,
   `baseline_queue.pid`, `baseline_queue.log`, and `active_runs.json`. Verify a
   PID's command before signalling. Never duplicate a queue or native solver.
   Exclude `ansyslmd.exe`: it is the license service, not a calculation.
3. The storage watcher runs continuously; `caffeinate -i -w <watcher PID>`
   prevents idle system sleep. Restore it if the watcher restarts, release at
   completion. Windows jobs use local `C:\IrisStudy\runs` and mirror accepted
   checkpoints to this Mac. Complete native files copy back at phase exit.
4. Never clean unrelated files. Only verified copies of this study's outputs
   can justify guest cleanup. Keep native databases/results ignored. No Git
   file or newly reachable blob may reach 100,000,000 bytes.

## Current native queue and recovery

All four coarse 20-row seven-second baselines are complete: 560 accepted steps
per case, no row removal, passed native energy/mass/hot-power audits. All four
same-mesh native/independent profile comparisons pass, largest difference about
1.035 K. These do not establish mesh-converged recession. All pilots also passed.

Two distinct refined-run issues must remain separate:

1. `sustainer_al_pulse7_n80_dt0125` failed at attempted 4.175 s / index 334 with
   10.420% energy residual. Last accepted: 4.1625 s / 333. Multiframe restart
   restores the initial database and does not retain EKILL/EALIVE. The old
   controller replayed pending kills only, allowing a removed row to return.
   Full-prefix replay fixed this: four-case native transient regression exactly
   matches uninterrupted temperatures and live counts. The valid manufactured
   fixture is `restart_topology_benchmark_v3`; earlier drafts are preserved.
2. `sustainer_al_pulse7_n80_dt0125_restartfix` then passed removal persistence
   (0.652% energy residual at 4.175 s, 396 live elements) and all 560 heating
   intervals through 7 s. BUT its first cooling interval internally split into
   substeps ending at 7.125, 7.19483 and 7.25 s. The endpoint audit mixed the last
   substep capacity/gas rate with the full macro conversion increment. All
   cooling from this chain is WITHDRAWN, despite its formerly passing threshold.
   The run was controllably paused around 57 s; raw state/checkpoints remain.
   Do not resume that chain. Its recent native backups are already in withdrawn
   cooling, so they cannot recover the valid 7 s state.

`validation/native_substep_audit_issue.json` records the second issue. A native
read-only result probe (`check_substep_gate.py`) verifies the exported substep
metadata and new gate: step 560/substep 1 is accepted, step 561/substep 3 rejected.
Retrospective log inspection confirms every previously published coarse baseline
and earlier pulse/restart control used one substep per macro; they are unaffected.
The corrected 7 s heating prefix was independently verified from its native log.

`configs/campaign_queue.json` has `verified_historical_prefixes` limiting the
old corrected run to index 560. The report capture and comparison helper honor
this cutoff; do not remove it or publish later raw checkpoints. Its historical accepted
heating comparison misses the separate 5 K hot-profile target (5.927 K at
7 s); conversion/mass targets are distinct. A one-macro-step removal timing
difference also remains visible. The withdrawn cooling comparison reached about
10.3 K and motivated inspection; it is not an accepted cooling result.

The initial `_substepguard` packages were prepared for all four cases; they
are now superseded by the midpoint-corrected packages described below. They
retain full deactivation replay, native live-count guards and two hash-verified
accepted native restart copies (`accepted_restart_0/1`). Revision
`full_removed_prefix_replay_v2_single_substep` additionally exports native load
step/substep identity and refuses acceptance unless there is exactly one native
substep per controller interval. The first second after the 7 s pulse uses
0.0625 s intervals; later cooling uses 0.25 s. Physics and balance gates remain
unchanged. Any further internal cutback stops acceptance; do not weaken the gate.

## Current material correction and dispatch (November 4, 06:29 UTC)

The paired default/tight 20 s controls are COMPLETE and audited (624 single
substeps each). Layer removal and cooling transfer pass. Their native profiles
differ by up to 6.986 K. Tighter nonlinear tolerance alone leaves a 5.173 K
comparison against the intended independent model; do not call that a pass.

A separate inherited material-source defect was identified: ANSYS `Temp` is the
current endpoint, so `Temp + 0.5*dTemp` is not the temporal midpoint. It is
endpoint plus half the increment. Replaying every accepted native temperature
through that formula reproduces conversion within 2.90e-8; intended midpoint
replay differs by up to 0.0182. Six native prescribed-temperature checks
(increasing, decreasing and constant) confirm this. The old isothermal tests
could not reveal the issue because dTemp was zero.

The native/independent temperature discrepancy has TWO causes. Repeating the
independent calculation with the actual inherited formula leaves 6.757 K
against default tolerance but only 0.2294 K against tighter tolerance. This is
a diagnostic reproduction, not a replacement for the intended midpoint model.
All earlier native thermal histories used the inherited formula. Keep them as
labelled historical numerical states, not corrected-model predictions. Earlier
independent midpoint refinement/sensitivity results remain separate and useful.

`model/usermatth.F` now uses `Temp - 0.5*dTemp`, and its paired DLL was rebuilt
with installed Intel Fortran Classic 2021.9 (oneAPI 2023.1), using ANSYS v261
build options. The isolated build is `ansystmp/builds/midpoint_v1`; source/build
hashes are in `validation/material_midpoint_build.json`. Six native checks with
the new library match midpoint conversion (max error below 2e-10). A corrected
80/20-cell sustainer Al 0.1 s motor pilot passed all eight audits and matches
independent temperatures within 0.00124 K. The inherited source is archived;
previous studies and every sealed runtime are unchanged.

The ONLY current primary dispatch is:
`sustainer_al_pulse7_n80_midpoint_tight` (127 s horizon).
Queue PID is in `baseline_queue.pid` (19823 when dispatched). This one-case queue
exits after acceptance so its corrected heating/cooling fields can be reviewed
before continuing the other three prepared `_pulse7_n80_midpoint_tight` cases.
They use 80 phenolic/20 case rows, 1e-5 heat-flow tolerance, the single-substep
guard and initial 0.0625 s cooling intervals. Booster horizons are 300 s.
`current_dispatch` and `deferred_midpoint_runtimes` in the queue record roles.
Never launch the superseded uncorrected packages. No second solver or queue.

Check the new case against the intended independent midpoint model at meaningful
accepted checkpoints and at completion. The new configuration pins material
source and DLL hashes; generation refuses a mismatch. Do not increase comparison
gates. Exact row scheduling remains a separate strict check. Then dispatch the
remaining corrected cases serially, followed by justified native time/mesh and
influential-input checks. A single pilot is not convergence of recession.

Evidence/scripts: `native_solver_tolerance_comparison.json`,
`native_temperature_convention.json`, `reaction_ramp_inherited.json`,
`reaction_ramp_midpoint_candidate.json`, and the two runtime-specific
`temperature_convention_resolution_*.json` records. The reusable helpers are
`compare_solver_tolerance.py`, `check_native_temperature_convention.py`,
`reaction_ramp_benchmark.py` and `build_material.cmd`. Do not run the inherited
replay diagnostic on corrected native states without changing its expectation.

The queue applies `validate_run.py` before advancing. Every accepted step,
manifest, native log, live count, restart-copy hash and v2 substep check must
pass. Zero native process exit code alone does not demonstrate acceptance.
Never edit sealed/running inputs. On another failure, preserve the directory,
use a matching accepted native/controller backup in a separate recovery sibling
with explicit source/configuration lineage, and verify the first resumed step.
Never pair rejected native state with an earlier controller checkpoint.

Production launch has nonce-matched guest receipts. A lost reply is recoverable
only if that exact receipt proves WMI launch success. Otherwise inspect native
processes and artifacts before any explicit reissue. Read-only storage queries
may retry; launch mutations must not retry blindly. Do not stop license services.

## Completed verification

- Four native steady cylindrical conduction checks, maximum error <0.013 K.
- Sixteen native constant-property topology states including first-row removal,
  last remaining row and exposed casing; max analytical error <0.000471 K.
  This static fixture did not exercise restart persistence; the new transient
  regression above fills that gap. Neither is a motor burnthrough result.
- Nine native isothermal UserMatTh checks at 300/600/1000 C and 0.1/1/5 s,
  maximum conversion error 1.72e-8. Eighteen documented warnings are nine USERCK
  and nine near-zero heat-flow reference warnings in the uniform-temperature
  fixture, not undisclosed solver failures.
- Controlled native pause at 1 s / resume to 1.1 s matches the uninterrupted
  reference exactly in temperature, conversion and energy integrals.
- Native one-second pulse plus five cooling steps passed boundary transfer,
  negative cooling heat flow and zero post-pulse char consumption/radiation.
- Guest-local pilot exactly matches the shared-drive pilot.
- Manufactured final-row controller event and storage-fault/latched-stop tests
  pass. The final event is software verification, not a physical prediction.
- Lost-launch-reply receipt tests cover matching, stale and missing receipts.

## Independent results and limits

`validation/radial/` contains independent radial finite elements, NOT ANSYS.
The assembly uses diagonal heat capacity, matching SOLID278 without advection.
Sources are archived in `validation/source_archive`. Never relabel independent
results as native output or a measurement. Keep compact source hashes in reports.

Twenty phenolic rows do not resolve recession. Seven-second 20/40/80/160-row
checks and time refinements quantify this. Consumed char retains live FE heat
capacity until whole-row removal: mass closure does not prove physical enthalpy
conservation. The retained thickness is a mesh geometry, not intact material.

`*_endurance_*` are REJECTED long-exposure numerical stress tests. Apparent
exhaustion times fail numerical/material-scope checks. Never report them as
motor lifetimes. Physically interpreted branches stop at provisional 150 C CF
or 300 C Al property-scope flags; neither threshold is a certified failure
criterion. No credible actual motor burnthrough time has been established.

Completed independent studies:

- `property_limit_convergence.json`: nominal continuous heating refined through
  320 cells and 0.00078125 s. Timing and remaining-thickness targets pass.
- 54 fine input scenarios at 80 cells / 0.003125 s: heating, radiation, removal
  cost, phenolic k/cp, pressure and supported CF surrogates. All stop at scope
  flags without exhaustion. Equation balances close; inputs remain exploratory.
- `input_sensitivity_refinement.json`: ten influential cases at 160 cells.
  Timing agreement alone initially concealed three thickness failures.
  `sensitivity_thickness_refinement.json` resolves low-k booster CF at 320 cells.
- Both `char_coupling_resolution_<case>.json` are NOW COMPLETE and pass. Doubled
  heating sustainer Al and booster CF need much smaller coupling steps: 320 cells
  at 0.0001953125 / 0.00009765625 s, then 640 at 0.000048828125 s. The joint
  comparison scales dt with pitch squared. At 640, scope stops are about
  39.879 s / 1.9422 mm (S Al) and 29.7066 s / 4.4648 mm (B CF). These supersede
  coarse stronger-heating recession estimates; calibration remains absent.
- `pulse_resolution.json`: 7 s pulse and cooling, native-like schedule through
  320 cells, with sustainer CF additionally at 640. Complete-case last joint
  changes <=1.61 K and <=0.0149 mm. S CF flag time changed 2.02% at its final
  refinement; an 80-cell native crossing is NOT already converged.
- Booster cooling extensions through 300 s capture later casing peaks around
  140--144 s; this motivated fresh native 300 s packages.
- `longer_pulse_refinement.json`: all eight hypothetical 20/60 s scenarios now
  complete at 160 and 320 cells. All numerical targets pass: flag times change
  <=1.05%, complete-history casing peaks <0.97 K, thickness <=0.020 mm. Cases
  stopping during heating did not complete the prescribed pulse within scope.
  Booster CF's 20 s case stops during cooling. These are not firing estimates.

The char-coupling and longer-pulse background jobs have finished. Their ignored
PID files remain historical; check actual commands before doing anything.
No independent solver needs duplicating. The capacity diagnostic below has also finished. Engineering perturbations are not
confidence intervals. Pressure screening changes only the assumed char closure,
with h/T fixed; its small effect is not real pressure insensitivity.

`partial_capacity_resolution.json` now contains twelve completed paired
independent 7 s pulse/cooling diagnostics at 80/160/320 phenolic cells. The
optional variant subtracts consumed surface-char density from heat capacity
ONLY; unchanged geometry/conductivity/source laws mean this is not a physically
conservative ablation model or a rigorous bound. At 320 cells complete-case
inner peaks shift <0.46 K and S CF scope time shifts 0.53%; retained mesh is
unchanged in every pair. At 80 cells S CF scope shift was 3.74%. The script is
`check_partial_capacity.py`; its PID/log are historical. Do not treat these
numbers as calibrated uncertainty or change the native material law to match.

## Remaining substantive work

1. Finish the corrected-midpoint, tight-tolerance four-case native pulse/cooling runs. Verify first-row
   removal persists through subsequent restarts, all energy/hot-load checks,
   live counts and restart copies. Check each terminal accepted record.
2. Rerun `compare_native_pulses.py` at meaningful checkpoints and completion.
   It compares accepted native fields only with the same-mesh independent
   model. Exact row scheduling is a separate strict check: a one-step event
   difference must remain visible even when field and mass targets pass.
3. Complete appropriate native time/mesh comparisons, especially sustainer CF
   cooling/scope timing, and native confirmation of influential supported
   sensitivity conditions. Use the completed independent refinement to choose
   useful cases rather than restarting the entire screening matrix.
4. Quantify partial-cell storage and valid model-scope bounds. Do not manufacture
   a finite lifetime by extrapolating material properties or tuning char laws.
5. Finish the English four-case comparison: heating duration/end time, retained
   thickness and mass, pyrolysis, casing peaks and times, numerical resolution,
   assumed-input sensitivity, calibration limits and answer to burnthrough.
   An inability to infer actual lifetime is a valid scientific outcome.

## Reporting and publication

`ansystmp/venv/bin/python docs/analysis/make_report.py` freezes accepted native
histories and compiles `output/pdf/iris_phenolic_report.pdf` using LaTeX. Run with
`PATH=/Library/TeX/texbin:$PATH`. The PDF skill was applied; its first-authoring
marker already ran. Render with pdftoppm and visually inspect every changed
page before publication. Check the TeX log. Do not publish an unreviewed PDF.

The report includes native temperature maps, casing curves, mass/energy audits,
independent/native profiles, sensitivity resolution and independent cooling/
longer-pulse scenarios. Failed steps and withdrawn cooling are excluded. The explicitly verified
7 s historical heating prefix remains shown until superseded by a fully verified
primary run; the queue cutoff must be honored by every capture/comparison.
Keep the native heating portion legible as longer cooling records arrive.

Publish major milestones using `model/publish.py '<milestone>' --push` after
checks. It stages Iris-only paths, checks storage and rejects files/new Git
blobs >=100,000,000 bytes. Never push native binary results or scratch.

The prior 15-page edition (`271f044`) withdrew unsupported cooling. The current
report additionally distinguishes the inherited reaction-temperature convention
from the corrected midpoint model and reports the native ramp and tolerance
checks. Its reviewed PDF hash and page count are in
`validation/report_visual_review.json`.

A 30-minute heartbeat, `iris-ansys-study-and-english-reports`, continues the
study. Notify only meaningful progress, failures, completion or necessary user
action. Keep it active while substantive work remains; stop on completion or
latched storage stop. Leave this file accurate for the next continuation.

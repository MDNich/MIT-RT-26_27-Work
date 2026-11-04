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
per case, no row removal, passed energy/mass/hot-power audits. All four native
profile comparisons against the same-mesh independent assembly pass; largest
profile difference is about 1.035 K. These are not mesh-converged recession
predictions. All four 0.1 s pilots also passed.

The first refined sustainer Al run, `sustainer_al_pulse7_n80_dt0125`, stopped
at attempted index 334 / 4.175 s: energy residual 10.420%, above the unchanged
5% gate. Its last accepted checkpoint is 333 / 4.1625 s. It had scheduled the
first removal at 4.15 s and passed the next hot-face audit at 4.1625 s.
The failed step is NEVER an accepted thermal result. See
`validation/native_restart_failure_diagnosis.json` for evidence and hashes.

Root cause: ANSYS multiframe restart restores the initial .rdb; .rnnn does not
save EKILL/EALIVE commands. The old controller replayed newly pending kills
only, so an already removed row returned on the following restart. The returned
row's capacity term explains the rejected energy residual. This is supported by
the v261 Basic Analysis Guide and reproduced by a native regression.

`restart_topology_benchmark.py` passed all four cases and sixteen checkpoints.
Corrected full-prefix replay exactly matches uninterrupted temperatures and
retains the right live count. The deliberately defective branch returns the
removed layer. Two earlier fixture drafts wrongly re-entered a new solution
for the continuous reference; they are preserved as rejected diagnostics.
The valid fixture is `ansystmp/runs/restart_topology_benchmark_v3`.

Fresh packages append `_restartfix` to all four refined names in
`configs/campaign_queue.json`. They retain the physical inputs and audit limits,
replay the entire removed prefix, verify native live counts before each solve,
and save two hash-verified accepted native restart generations in
`accepted_restart_0` and `accepted_restart_1`. The old failed and unstarted
packages remain unchanged. The original native ring contained only latest r001
and early r002--r006, so no recent accepted native restart was available; a fresh
run was justified by the reproduced defect, not by blindly retrying a failure.

The corrected serial observer started November 4 at 05:30 UTC, PID recorded in
`baseline_queue.pid` (5304 at launch). It runs only the four new packages:
sustainer Al, sustainer CF, booster Al, booster CF. Sustainer cooling horizon is
127 s; booster horizon 300 s to capture late casing peaks. All heat for 7 s;
stop earlier at the provisional casing-property flag. Initial mesh: 80 phenolic
and 20 casing rows, two axial and two angular divisions. Check the actual log
and live processes rather than relying on this recorded PID/time.

The queue applies `validate_run.py` before advancing. Every accepted step,
manifest, native log and new live-count/restart-copy check must pass. A native
exit code of zero alone is insufficient: the controller can deliberately exit
on a failed audit. Do not weaken limits or edit sealed packages. If another
failure occurs, preserve the failed directory and diagnose it. Recover in a
separate sibling with matching accepted controller/native state, verified
manifest and documented provenance; never pair rejected native state with an
earlier accepted controller state. The two backup manifests identify complete
copies; do not trust an interrupted slot whose file hashes fail.

Production launch uses a unique guest receipt. A lost Parallels reply is
recoverable only if the receipt matches that request and proves WMI success.
Without that proof, inspect processes and guest artifacts before any explicit
reissue. Do not blindly retry launches. Read-only storage queries may retry.
Prior observed InvalidArgument dispatch failures and explicit recoveries remain
recorded locally and in verification records.

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
No independent solver needs duplicating. Engineering perturbations are not
confidence intervals. Pressure screening changes only the assumed char closure,
with h/T fixed; its small effect is not real pressure insensitivity.

## Remaining substantive work

1. Finish the corrected four-case native pulse/cooling queue. Verify first-row
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
longer-pulse scenarios. Failed native steps are excluded. Superseded refined
runs are described in the failure section, not overlaid as current runs.
Keep the native heating portion legible as longer cooling records arrive.

Publish major milestones using `model/publish.py '<milestone>' --push` after
checks. It stages Iris-only paths, checks storage and rejects files/new Git
blobs >=100,000,000 bytes. Never push native binary results or scratch.

A 30-minute heartbeat, `iris-ansys-study-and-english-reports`, continues the
study. Notify only meaningful progress, failures, completion or necessary user
action. Keep it active while substantive work remains; stop on completion or
latched storage stop. Leave this file accurate for the next continuation.

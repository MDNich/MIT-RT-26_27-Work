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

## Current material correction and dispatch (November 4, 08:53 UTC)

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

The corrected sustainer Al primary is COMPLETE through 127 s: all 1,052
intervals passed the native audit, live-count/substep checks, sealed inputs and
accepted restart hashes. Maximum energy residual is 0.03468 percent; maximum
hot-load relative error is 8.52e-7. The full intended-midpoint independent
comparison passes: maximum live-profile difference 0.333432 K and conversion
difference below 0.00028. Both remove the first row at 4.1625 s and transfer
the load at 4.175 s. All cooling transition checks pass.

For that imposed seven-second pulse, retained mesh is 4.70296875 mm. Sampled
inner/outer casing peaks are 120.4973 C at 79 s and 120.4771 C at 79.25 s.
These are 80-row exploratory numerical results, not actual motor lifetime or
completed native mesh convergence. The old queue PID 19823 exited normally.

The corrected sustainer CF primary is now COMPLETE at its material-scope flag:
680 accepted intervals through 34 s, with the last bracket [33.75, 34] s.
The inner casing reaches 150.06349 C; the outer surface is 112.87941 C.
Retained mesh is 4.70296875 mm. Full native validation and the independent
comparison pass (maximum live-profile discrepancy 0.333445 K), with identical
first-row scheduling and cooling controls. Do not call this burnthrough or
structural failure; absolute timing remains mesh- and cutoff-dependent.

Its native log includes a material-table warning at 21.9999998 C, about
2e-7 K below the initial table endpoint, in addition to USERCK and elapsed/CPU
performance warnings. This negligible undershoot is recorded. ANSYS ceased
repeated table-range checking; the controller still checked the explicit
150 C model-scope limit at every accepted interval.

The corrected booster Al primary is COMPLETE through 300 s, accepted by the
queue at 08:01 UTC: 1,744 audited intervals, maximum step energy residual
0.06314 percent and hot-load relative error 8.50e-7. Full independent profile
comparison is 0.22042 K, with identical first-row scheduling at 4.600 s and
first transferred boundary at 4.6125 s. Native topology and cooling checks pass.
Retained mesh is 6.270625 mm; sampled inner/outer casing peaks are
84.78386/84.76535 C, both at 142.75 s. No exhaustion occurred in the prescribed
seven-second heating pulse and cooling through 300 s. This is a conditional
80-row result, not completed native mesh convergence or a real firing lifetime.
Its log warnings are USERCK and elapsed/CPU performance; no solver error.

Corrected booster CF is COMPLETE through 300 s, accepted at 08:47:40 UTC.
All 1,744 accepted intervals, sealed inputs, restart copies and native logs
passed the full audit. The independent comparison passes through the endpoint
(maximum profile difference 0.22042 K), with identical first-row scheduling at
4.600 s, transfer at 4.6125 s, persistent topology and cooling checks. Maximum
step energy residual is 0.06314 percent; maximum hot-load error is 8.50e-7.
It retains 6.270625 mm of mesh. Sampled inner/outer casing peaks are
114.24317 C at 102.75 s and 105.13083 C at 144.25 s. These are conditional
80-row histories; no actual firing or lifetime is inferred.

Its warnings are USERCK, elapsed/CPU performance and the same negligible
21.9999998 C KXX-table undershoot seen in sustainer CF. This is about 2e-7 K
below the table endpoint. Native repeated range checking ceases, but the
controller continues the explicit property-scope guard at every accepted step.

All four corrected primary cases have reached audited stopping points. The
existing queue completed sustainer_al_pulse7_midpoint_time_quarter at 11:02 UTC
and advanced to sustainer CF quarter-step. No queue or solver was duplicated.
Twelve native resolution cases remain, followed later by the five prepared
sensitivity/cutoff controls below. The first quarter-step run passed all 4,208
accepted intervals through 127 s, removal/cooling controls and the independent
comparison (maximum profile difference 0.09913 K). Its first native time-only
comparison changes casing peaks by 0.721 K with unchanged retained mesh;
this does not establish native spatial convergence.

The ONLY active serial queue is PID 26648 at dispatch (always verify its actual
command using baseline_queue.pid). It began at 06:57:11 UTC with the following ordered dispatch:

1. The three primary cases then remaining: sustainer CF, booster Al and
   booster CF, with suffix _pulse7_n80_midpoint_tight. All are now complete.
2. Four 80/20-row time_quarter cases.
3. Four 160/40-row space160 cases.
4. Four 320/80-row joint320 cases.
5. Sustainer CF 640/160-row joint640.

The latter thirteen packages were structurally checked, sealed and verified
to preserve physical inputs and audit gates. Their definitions are in
validation/native_resolution_plan.json; generation is reproducible with
model/prepare_native_resolution.py. Heating steps are 0.003125 s for the
time-only/160-row cases, 0.0015625 s at 320 and 0.00078125 s at 640. The first
cooling second uses five times those intervals, then respectively 0.0625,
0.03125 and 0.015625 s. Sustainer horizons are 127 s, boosters 300 s, subject
to property-scope stops. Never edit or regenerate a sealed/running package.

The current_dispatch field records the exact sixteen-job continuation. Primary
inputs use 80/20 rows, 1e-5 heat-flow tolerance, the single-substep guard and
initial 0.0625 s cooling intervals. No second solver or queue. Never launch
superseded uncorrected packages.

Check cases against the intended independent midpoint model at meaningful
accepted checkpoints and at completion. Configurations pin material source
and DLL hashes. Exact row scheduling remains a separate strict check; never
increase comparison gates. Five influential-input/cutoff native controls are prepared below; their
execution remains deferred until the current serial queue exits.

The queue now requires both validate_run.py and compare_native_pulses.py
with --require-pass before advancing each corrected case. The independent
gate includes native topology/cooling controls in addition to profile,
conversion, mass and exact row scheduling. Refinement outputs use runtime-specific
comparison files so they cannot replace primary case records.
Run model/compare_native_resolution.py as completed cases arrive; it reports
only terminal audited records, compares censored histories by scope time rather
than an uncomputed peak, and retains failed intermediate refinements visibly.
It now has five completed records: the four primaries plus sustainer Al quarter-step.
The first time-only comparison passes: inner/outer casing peak changes are
-0.72076/-0.72055 K, with unchanged retained mesh. Twelve refinement cases remain;
sustainer CF quarter-step is active. No spatial convergence is inferred yet.

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

## New combined-input and removal-cutoff checks

All independent workers from this continuation have FINISHED. Their ignored
PID files are historical: combined_sensitivity.pid (29899), removal_cutoff.pid
(33020), tight_cutoff.pid (33883). Never duplicate them from a stale PID file.

- combined_pulse_sensitivity.json: eight joint-input seven-second pulses,
  each at 80/20, 160/40 and 320/80 phenolic/casing cells (24 calculations).
  The transport combination uses h=2000, phenolic k x1.2 and cp x0.8. The
  consumption combination uses h=2000, k x0.8 and removal cost x0.5. All eight
  final 160-to-320 comparisons pass: peak shifts <=0.856 K, scope time change
  about 0.259 percent, retained thickness <=0.01985 mm. Only sustainer CF's
  transport combination reaches the property flag; none exhausts the liner.
  These are independent engineering scenarios, not a confidence envelope.
- removal_cutoff_sensitivity.json: 24 paired independent runs at 160/320 cells
  with residual-solid fractions 0.0001, 0.001 and 0.01. At 320 cells, CF scope
  time shifts -7.21 to +16.12 percent relative to the default 0.001; complete
  casing peaks shift by up to 3.812 K. A mass-ledger check concealed this
  numerical/model sensitivity. The 1-percent setting is an independent
  diagnostic only, not an input approved by the native package guard.
- removal_cutoff_resolution.json: another 24 records at 320/640 cells and
  fractions 1e-4, 1e-5 and 1e-6, reusing identical cached records where possible.
  Every final cutoff and mesh/time comparison passes the stated targets.
- removal_cutoff_tail_sustainer_cf.json: two additional fixed-640-cell runs
  at 1e-7 and 1e-8. Scope times are 24.765625 and 24.390625 s; changes from
  the preceding decade are about -1.369 and -1.514 percent. These are NOT
  replacement native results or physically validated cutoff choices.

The finite cutoff is a modelling rule for residual ejection/loss of continuity,
not simply a tolerance whose zero limit is automatically physically correct.
Available-char capping implies solid density >= rho_v*(1-alpha), and the
first-order reaction leaves 1-alpha positive at finite integrated exposure.
Exact zero residual is therefore not reached in finite time in the continuous
equations. Preserve this limitation; do not promote a tighter cutoff to a
calibrated erosion law or silently replace the sealed native inputs.
The existing thirteen native resolution jobs still quantify mesh/time changes
at the documented fixed default rule. Their results must remain conditional.

native_uniformity.json checks every accepted primary checkpoint for same-radius
axial/angular variation. Both completed Al cases are essentially uniform; maximum sustainer CF
phenolic/casing spreads are about 0.00654/0.0130 K. Booster CF spreads are
0.00575/0.01039 K. This checks the radial
averaging of the uniform-sector calculations, not uniformity of a real motor.

Five later native controls are prepared and NOT in the active queue:
- Four bounded sensitivity controls in native_sensitivity_plan.json, generated
  by prepare_native_sensitivities.py; they end at 20 s or the earlier property
  flag. They test higher heating, the alternative CF radial tuple and two
  combined cases. The alternative CF changes density, radial k and constant
  cp while retaining the baseline in-plane conductivity.
- sustainer_cf_cutoff1e6_midpoint_control60, recorded in native_cutoff_plan.json.
  It tests fractional cutoff 1e-6 through 60 s or the earlier scope flag.
  Compare with the queued sustainer_cf_pulse7_midpoint_time_quarter default
  case at identical time/mesh settings; the different horizons do not affect
  a shared earlier material-scope stop. This tests implementation, not the
  physical correctness of the tighter cutoff.

The campaign records deferred_sensitivity_runtimes and deferred_cutoff_runtimes.
Dispatch them only after the current serial queue exits and review permits it;
never create a second observer or native solver. All use the existing native
and independent acceptance gates. Keep runtime-specific comparison files.

## Remaining substantive work

1. Complete the twelve remaining queued native time/mesh checks. Preserve the strict
   native acceptance gates, exact row scheduling, restart topology and independent
   comparison at every terminal record. Keep all four primary results intact.
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

The 58532b6f milestone published the completed booster Al history. The current
edition completes the primary four-case comparison with booster CF through
300 s, explicit times of inner/outer casing maxima, four completed uniformity
checks and the recorded negligible table-endpoint warning in both CF cases. It freezes accepted
states and explicitly separates independent results and historical states.
Its reviewed PDF hash and page count are in validation/report_visual_review.json.

The user requested substantially fuller physics documentation and printed code,
and questioned the inner temperature. The new technical section derives the
implemented reaction/transport and FE equations and prints exact source listings.
Do not erase these details in later automated builds. `technical_details.py`
verifies sealed input hashes, archives all four primary small input decks under
`docs/analysis/source_listings`, and adds heating-only temperature and 7 s radial
profiles. The complete sustainer Al mesh/driver/export, full Fortran and controller
are printed; CF differences use original source line numbers. This is documentation,
not a new simulation or a change to the existing queue.

Temperature checks: the imposed gas is 2504 K; primary exposed phenolic peaks are
about 1480-1488 C and at 7 s about 1452-1466 C. The 85-150 C values refer to casing
heat soak, and the final snapshot hot-face values occur after cooling. Always
name location, time, units and mean-versus-maximum. `temperature_interpretation.json`
pins the native checkpoint/accepted-record hashes and verifies endpoint convection
against actual native face rates. No claim of physical calibration follows.

The first native time-only pair also needs a surface-specific caveat: sustainer Al
T_s at 7 s changes from 1466.032 to 1422.376 C (43.656 K), despite a casing-peak
change of only 0.721 K. Its sampled hot peak changes 1479.604 to 1479.335 C;
the maximum matched heating-history discrepancy is 48.688 K at 0.0125 s.
`native_hot_surface_time_comparison.json` reports this separately. Continue to
assess hot-face histories and row-transfer times during refinement; a passing
casing-target comparison does not establish hot-surface time convergence.

A 30-minute heartbeat, `iris-ansys-study-and-english-reports`, continues the
study. Notify only meaningful progress, failures, completion or necessary user
action. Keep it active while substantive work remains; stop on completion or
latched storage stop. Leave this file accurate for the next continuation.

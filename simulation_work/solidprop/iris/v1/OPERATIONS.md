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

## CF end-of-exposure native inputs, November 5, 22:07 EST

Six ten-core SOLID278 decks now cover the last part of each CF exposure.
Their starting point is the first 1000 °C backing crossing in the audited
reacting CF model, 95.08 s or 129.70 s. At those instants the residual virgin
fraction of the retained liner mass is below 0.0006 percent in both motors.
These checks approximate the remaining phenolic as pure char and prescribe
the archived casing interface history. Each solve updates the hot face,
char reaction, film reduction, radius and remeshed enthalpy. The supplied
backing trace is held at its last value if a check extends beyond the trace.
ANSYS integrates the thermal state of the char sector; the source histories
are independent-model inputs. The two Al tails still contain about five percent
virgin material by mass at complete casing melting, so these CF-only inputs
must not be reused as Al checks.

The package is `configs/native_verification/cf_tail_char_smp10/`. Mesh/time
pairs are 20 rows at 0.04 s, 40 at 0.04 s and 40 at 0.02 s. The initial mass
substitution, initial enthalpy difference, independent FE history and horizons
are recorded per deck. The output reader checks all start/end nodal fields,
all increments, kinetic flux, radius, applied face power, backing heat reaction,
total storage, and donor-to-recipient remap. Six synthetic exports and damaged
copies exercised the gates. There has been no native end-window solve yet.
After both manufactured checks and all four frozen-field receipts, use the same
guarded dispatcher for tails204, tails404, tails402, tailb204, tailb404, tailb402
in order. Before accepting these results, inspect solver property/mesh warnings
and heat-balance checks. A matched terminal segment cannot validate the
preceding heating history or casing strength.

## Reacting CF results, November 5, 21:55 EST

Worker 61181 completed all eight independent moving-wall jobs and exited.
`validation/cf_backing_audit.json` checks all profiles, native-independent
separation, separate casing and liner mass ledgers, total enthalpy, event
intervals, refinements and restart. At 640/160 cells the sustained model
exhausts the CF liners in 104.254 and 137.946 s. The first backing temperature
of 1000 °C precedes exhaustion in both. Further extension assumes the property
endpoints and a retained, venting composite. Nominal four-case results,
sensitivities and the conduction audit appear in the updated report.

Do not rerun the completed independent matrices. The native sequence, starting
with CF320 under observer 28607 and continuing with annular, char8, char16 and
four R2 snapshots, remains outstanding. Full continuous thermochemical FE
coupling is a separate verification requirement.

## Native sector preflight, November 5, 21:44 EST

The original four frozen-field decks left the element's heat-capacity option
at its default. In a SOLID278 conduction analysis the default uses diagonal
storage, while these checks specify a consistent capacity matrix. The first
package was never dispatched. Only `motor_snapshots_30s_smp10_r2` may run.
Its decks explicitly select KEYOPT(15)=2 and backward Euler. The official
[ANSYS element reference](https://ansyshelp.ansys.com/public/views/secured/corp/v261/en/ans_elem/Hlp_E_SOLID278.html)
documents the option.

A separate three-dimensional brick assembly read the printed connectivity,
coordinates, initial temperatures, source and boundary loads of each deck.
All four sets of 9,090 nodal comparisons against the independent radial
reference passed before native execution. The reader checks native storage
against the total applied energy at each increment as well as ring spread and
all nodal temperatures. See `validation/native_snapshot_preflight.json`.
The same guarded dispatcher recognizes the four motor names after annular,
char8 and char16 have successful native receipts. Its native motor order is
sustainer Al, sustainer CF, booster Al, booster CF. The existing CF320
observer alone owns the current native run.

## Native verification handoff, November 5, 21:37 EST

The sole native job is still the 320-row sustainer CF pulse under its active-only
observer. The 02:38 UTC prefix passed through 5.53281 s and both row-transfer
checks passed. After it exits, check the terminal acceptance, cooling comparison and
queue receipts. Use `model/run_native_wall_verification.py CASE readiness`
to check these receipts, the registry, storage and solver occupancy. Run
`launch` once for an eligible case and `collect` after guest completion. An
ambiguous launch requires inspection of the existing intent and guest job.
The order is `annular`, `char8`, then `char16`. All three PowerShell wrappers
passed a guest parse check. Synthetic exports exercised every nodal field and
the removal ledger in the moving-char reader, including ten deliberately broken
exports. Native verification of those fields is still pending.

Four 30 s fields from the audited nominal moving-wall runs now have sealed
native comparison decks in `configs/native_verification/motor_snapshots_30s_smp10/`.
Each uses 80 liner rows, 20 casing rows and ten 0.005 s increments. Geometry,
reaction rates, properties and surface loads are held at the donor state.
Compare every node against the consistent-capacity reference in the matching
JSON. The lumped-capacity result is an additional diagnostic. These inputs test
conduction and energy storage for actual motor temperature gradients.
A native run that couples surface motion to evolving material and surface loads
is still required to verify a continuous-heating liner exhaustion time.

## Material comparisons, November 5, 21:27 EST

The ten retained-Al integrations under worker 52320 completed and the worker
exited. Check `ansystmp/aluminium_backing_campaign/complete.json`,
`configs/aluminium_backing_campaign.json` and `validation/aluminium_backing_audit.json`.
All eight comparisons meet event, thickness and interval-overlap gates.
The updated report includes the ordering of melt and liner events and the
separate CF resin response. No further dispatch of these ten cases is needed.
The CF diagnosis uses archived temperatures, competing resin kinetics and two
interpretations of a published catalyst coefficient. Couple the backing heat
and gas budgets before changing the reported CF liner times. Keep heat-transfer
uncertainty, the original material flags and actual casing strength distinct.

The 02:11 UTC CF320 native prefix passed through 4.73594 s. Observer 28607
still owns the original CF320 case and its terminal checks. After its successful
audits and exit, proceed first to the sealed annular conduction benchmark.
Two later manufactured continuous heating cases with a free, nonuniform
pure-char wall are prepared under `configs/native_verification/moving_char_log_smp10_r2/`.
Only this revision may be dispatched, in separate fresh run directories, coarse
before fine. The preparation-only first revision is retained to identify the
corrected facet gradient, scalar MAPDL export and supported parameter functions.
The manufactured gas law balances conduction and reaction on a logarithmic field.
The exact event of this thin coupon is solely a verification target.
Preserve native result and warning gates, monitor storage and use one ten-core
process. The new decks have undergone static readback only.

## Current handoff, November 5, 21:02 EST

All three independent moving-wall workers exited. Their completion receipts are
under `ansystmp/moving_surface_{campaign,sensitivities,endpoints}`. The
three completed matrices contain 20, 42 and 16 records respectively. Do not
restart them or regenerate their parent audits or sealed plans.
`validation/moving_surface_endpoint_audit.json` includes 16 new fine-case
balances and comparisons against the corresponding 320/80 or coarser-time
case. All sixteen meet the event-time and remaining-thickness targets. One
booster Al high-film time-step pair misses strict final-step overlap (0.0073 s
event difference). Fifteen overlap. Keep this exception visible.

Read the current 12-page continuous-heating report and its input receipt.
At 02:00 UTC the CF320 native prefix passed through 4.39375 s, step 2812.
Observer 28607 owns the only active solve. Keep its terminal, restart and
topology audits separate from the moving-wall results. After it exits and all
guest process checks pass, use the sealed inert annular verification input
described below. Then compare a continuous-heating native calculation under
matching surface and enthalpy equations against the independent solution.
Do not dispatch the deferred pulse queue.

The recorded casing flags precede every exhaustion event. Next extend the
thermal backing physics with phase-change enthalpy for a documented Al
surrogate and a material-specific decomposition treatment for CF. Journal
these surrogate and property-limit events separately from liner exhaustion.

### Two verification preparations, November 5, 21:08 EST

The annular MAPDL benchmark reader accepted an analytical fixture and rejected
nine faulty exports or logs (including wrong core count, duplicate/missing
node, excessive field error and wrong end time). This is a reader check only.
For the future guest run use job `irmode64`, output `irmode64.out`, and index
the run for the storage watcher. Archive the guest deck, log, `mode_time.txt`
and `mode_end.txt` in `ansystmp/runs/annular_mode64_smp10/`. The wrapper must
record `guest_terminal.json` with job, exit_code, guest_input_sha256 and
guest_sha256 (the three named exports). Compare in-guest and copied bytes.
Use `model/audit_native_conduction_mode.py audit` only after the real process
exits. The gate requires the original analytical time, 585 distinct nodes,
the sealed 0.25 K field tolerance and a normal ten-core termination. Any solver
warning goes to review. Never use synthetic fixtures as native output.

`model/aluminium_phase_enthalpy.py` supplies a separate pure-metal caloric
reference. The crystal and liquid enthalpies use the same NIST-JANAF Al-001
table reference. The manufactured checks recover isothermal partial melting,
test tabulated enthalpy differences and close the smoothed transitions for
0.5, 1, 2 and 4 K widths. See `validation/pure_al_phase_enthalpy.json`.
The material module has not yet been coupled to the accepted motor cases.
Use a separate backing scenario and source manifest, verify it with a heated
coupon, refine the transition width and time step, and record first/complete
melt independently. Fixed geometry past melting assumes the backing stays in
place. Continue to report the earlier 300 C flag. Conductivity and actual
alloy/temper remain separate material inputs.

## Moving-wall numerical audit, November 5, 20:53 EST

All twenty nominal moving-wall refinements completed and worker 43139 exited.
`validation/moving_surface_campaign_audit.json` checks sealed sources, per-case
final checkpoints, profiles, shared-time thickness/temperature histories, mass
and open-system energy. At 640/160 cells and a 0.02 s ceiling the S Al/S CF/B Al/B CF
liner-exhaustion times are 106.774/103.934/142.409/137.663 s. These independent
hypothetical intact-backing events all follow the earlier property flags.
All four finest fixed-step mesh pairs and all four finest fixed-mesh time pairs
pass the event-change and thickness targets and have overlapping final-step
brackets. Three coarser comparisons miss strict bracket overlap. The discrete
instantaneous hot-face temperature after the load step remains mesh-sensitive.

The separate one-factor sensitivity matrix is now running under PID 44706
after nominal worker completion. It uses the same exclusive lock. See
`configs/moving_surface_sensitivities.json` (sealed),
`ansystmp/moving_surface_sensitivities/{worker,status,complete,error}.json`,
and `worker.log`. It checks 42 independent perturbations at 320/80 and 0.04 s.
Read back source/configuration identities, per-case balances, first property
flags and event brackets; refine the influential endpoints before presenting
any span as a numerically checked sensitivity result. Never treat one-factor
extrema as firing uncertainty bounds. No additional native solver was started.

## Coupled moving-wall campaign, November 5, 20:48 EST

The prior continuous finite-row workers have exited. A new independent worker
for the coupled model, PID 43139, uses the same exclusive worker lock. Check
`ansystmp/moving_surface_campaign/worker.json`, `status.json`, `worker.log`,
`error.json` and `complete.json` and verify the actual process before acting.
Use `configs/moving_surface_campaign.json` as sealed. Source hashes and the
manufactured verification receipt are pinned; never regenerate or edit this
plan. The new runner resumes its own checkpoints and refuses mismatched inputs.
The historical independent 960 s horizon remains a cap; stop each case at
geometric exhaustion. Keep the inherited 150 C CF/300 C Al crossings separately.

Candidate component and coupled synthetic tests pass. A nonuniform synthetic
CF-backed coupon resumed byte-identically after the first property flag and
after cell mergers. No new ANSYS solve was dispatched. Only CF320 is active on
ten cores under observer 28607. Complete its terminal audits before launching
the already sealed inert annular native benchmark. See the following handoff.

## Current handoff, November 5, 20:31 EST

The independent refinement worker 31732 completed all eight fresh integrations
and exited. Inspect `ansystmp/continuous_heating/refinement_complete.json`
and `validation/continuous_heating_refinement_audit.json`. Do not relaunch it.
The four 320/80 cases end at 115.0961, 112.3000, 151.9516 and 147.2656 s
(S Al, S CF, B Al, B CF). Maximum isolated change in final time is 0.7834%;
all eight event brackets are disjoint and the sustainer thickness discrepancies
reach 0.05953 mm against a 0.047625 mm target. Post-property-flag events are
qualified numerical continuations only. See the seven-page progress report.

The native queue still contains only the active CF320 case under observer
28607. At 01:24:45 UTC its prefix audit passed through 3.315625 s and the
first transferred row was verified. The observer owns its terminal checks.
When complete, verify terminal, restart, topology/transfer and cooling gates
before recording completion. Never resume the superseded pulse queues.

Candidate component receipts cover cylindrical remap, reference-state
enthalpy/reaction, mixed hot-face balance and transient diffusion. A synthetic
coupon restart reproduced the entire terminal dropout history and byte-identical
checkpoint. Next implement the coupled transient moving-boundary driver,
check space-time mass/energy closure including the last shell, and run
independent mesh/time event studies. Keep final exhaustion under an unvalidated
backing distinguished from an assembled motor lifetime.

A separate inert annular-mode native input is prepared in
`configs/native_verification/annular_mode64_smp10/`. It has 585 nodes,
256 SOLID278 elements, 256 time substeps, and a per-node analytical endpoint.
Use `model/prepare_native_conduction_mode.py verify-input` for readback.
This package has not run. After the active-only observer exits, verify no
guest solver/wrapper remains, use a fresh study-only guest directory and one
ten-core SMP launch with storage monitoring. Verify the deck hash on the guest,
normal termination, requested cores, warnings, time, all node IDs/temperatures,
and the frozen 0.25 K criterion before recording a native result.

## Burnthrough priority revision (November 5, 19:53 EST)

Read `burnthrough_campaign_plan.md` before choosing more work. The user explicitly
authorized choosing exposure duration, moving beyond seven seconds, answering
time to burnthrough and improving the model. This supersedes the previous
requirement to finish every pulse refinement before long-exposure work.

The host-only observer 93981 was terminated after confirming its exact command
and absence of child processes. **The native solver was not stopped or changed.**
Replacement observer **28607** monitors only the already-running
`sustainer_cf_pulse7_midpoint_joint320_geom005_smp10`, using its existing launch
receipts, then performs the normal terminal audits and exits. Its log is
`ansystmp/burnthrough_priority_active_verification.log` and receipt is
`validation/burnthrough_priority_transition.json`. Watcher 82419 and keep-awake
86412 remain in place. Never resume observer 93981 or the superseded queue.

The three unstarted pulse refinements are now in
`deferred_pulse_resolution_runtimes`. The five old sensitivity/cutoff controls
also remain deferred. The next native dispatch must support the continuous-
heating/moving-surface study and pass the new plan's gates, after the current
solver exits. Native input packages remain sealed and one solver at ten cores
is still the maximum native concurrency.

The new independent campaign is `model/continuous_heating_campaign.py`, with
immutable `configs/continuous_heating_campaign.json`. Its `prepare` action has
already run; do not regenerate. Its `run` action uses a nonblocking worker lock
and can resume its ignored checkpoints under `ansystmp/continuous_heating`.
Read `worker.pid`, `status.json`, `worker.log`, and any `worker_error.json` or
`complete.json` before doing anything. Verify PID commands; do not duplicate it.
Compact outcomes go to `validation/continuous_heating/`. These are **independent
mathematical scouts**, not native ANSYS or physical lifetime results.

The scout worker was launched with PID **29748**. Eight following refinement
checks are prepared in `configs/continuous_heating_refinement.json`; do not
regenerate that plan. `model/continuous_heating_refinement.py run` requires the
scout completion receipt and the same exclusive worker lock. Inspect
`refinement_worker.pid`, `refinement_complete.json` and `refinement_error.json`
before dispatch/resume. They isolate fixed-mesh time error and then fixed-step
mesh changes. A prepared plan is not a running calculation or a passed gate.

At 20:05 EST the four scouts finished normally and PID 29748 exited.
`validation/continuous_heating_scout_audit.json` rechecks source/configuration
hashes, checkpoint states, monotone histories, exhaustion bookkeeping and
cumulative gas/char/residual mass. Maximum cumulative mass relative error is
1.54e-14. New model-event times are 114.946875 / 112.181250 / 151.696875 /
147.046875 s for S Al / S CF / B Al / B CF; corresponding property flags are
49.6000 / 18.465625 / 87.3671875 / 32.88125 s. **These are unvalidated finite-row,
post-scope mathematical events; do not put them in physical-lifetime tables.**
The earlier rejected endurance records remain rejected.

The refinement worker **31732** started only after scout exit and audit. It uses
the same exclusive lock, logs to `ansystmp/continuous_heating/refinement_worker.log`
and updates the common `status.json`. Scout `complete.json` is historical;
look for `refinement_complete.json` to establish completion of this next stage.
Inspect errors before resume. Do not duplicate either worker from old PID files.
The separate four-page `output/pdf/iris_continuous_heating_progress.pdf` contains
the provisional results and full tested remapping-kernel source. Its review
and input provenance are in `validation/continuous_report_inputs.json`.

They keep continuous nominal heating and record rather than stop at the first
casing-property flag. Preserve the explicit post-scope qualification. Earlier
rejected endurance runs must not be promoted. A short restart-control check
is in `validation/continuous_heating_worker_verification.json`.

While these scouts run, implement and verify the conservative moving-surface
candidate specified in the new plan; do not spend subsequent turns merely
polling or add another large seven-second matrix. Reuse completed short-time
fields as regression evidence. Publish new setup/model/result milestones with
the existing limits. The current 78-page PDF remains the earlier reviewed
results edition until the next meaningful tested-model or accepted-result update.

The first candidate component, `moving_surface_remap.py`, now passes analytic
geometry/conservation checks in `moving_surface_remap_verification.json`. It
preserves extensive mass/enthalpy, reports swept-out quantities and locates a
prescribed-speed exhaustion event. It is **not yet a coupled thermal/pyrolysis
model or native ANSYS implementation**. Its 100 s manufactured example must
never enter motor-result tables. Next implement the enthalpy reconstruction and
surface mass/energy closure before treating this as a replacement solver.

## Active corrected-geometry resolution queue (November 5, 19:10 EST)

This dispatch description is historical and superseded by the priority revision
above. Its completed results remain valid within their stated qualifications.

Sustainer Al320/80 completed 127 s / 8416 accepted intervals. Repeated full
native/log/restart validation exactly reproduced the queue acceptance record;
all 22 independently compared checkpoint hashes were rechecked. Maximum sampled
native/reference profile difference is 0.015045902 K. Three row-removal events
at 3.1421875, 5.2015625 and 6.315625 s match the independent schedule exactly;
their next-step transfers, persistent topology and cooling transition pass.
The maximum native energy residual is 2.72316e-5 relative, hot-load error
5.88639e-8 and absolute mass residual 1.05673e-21 kg. The final log has zero
errors and the documented USERCK and generic elapsed-time/SMP advisories.

Sampled inner/outer casing peaks are 123.850357/123.829494 C at
77.78125/77.875 s, with 4.7178515625 mm retained mesh. Against the corrected
160/40-row case, peak changes are 1.604934/1.604579 K and retained thickness
changes by 0.0148828125 mm, below the 5 K and 0.047625 mm targets. Physical
inputs, sector geometry/measures and native tolerance are identical; radial
resolution doubles while heating/cooling steps halve. This is a joint mesh/time
comparison, not isolated spatial convergence or a calibrated lifetime. The
hot-face history is assessed separately in the updated report. At 7 s its mean
changes by +5.231525 K, but the maximum shared-sample heating discrepancy is
165.810022 K at 1.24375 s (1056.067296 versus 1221.877318 C). Both cases still
have zero removed rows at the same radius then, so this discrepancy is not
solely a row-transfer jump. The coupled surface history remains unresolved
even though the stated casing/thickness targets pass; preserve this distinction
when assessing the remaining finer cases.

All 8416 full temperature fields were checked: maximum same-radius ranges
are 1.64466e-8 K in live phenolic and 1.17240e-12 K in casing. These describe
numerical uniformity in the prescribed sector, not real-motor hot spots.
The accepted, independent and full-field records use the complete runtime
name `sustainer_al_pulse7_midpoint_joint320_geom005_smp10` in `validation/`.

The unchanged observer **93981** advanced normally to
`sustainer_cf_pulse7_midpoint_joint320_geom005_smp10`. Four resolution cases
remain in `current_dispatch`, followed by five deferred controls. Initial
accepted CF320 states and the actual single ten-core SMP process have been
verified. Keep watcher 82419 and keep-awake 86412. Never resume superseded
observers or modify sealed packages. The earlier CF scope-time failure still
requires its 320/640 comparisons; a 150 C scope flag is not failure/burnthrough.

At 19:10 EST, the completed sustainer Al320 guest `file.rth` was removed only
after full Mac/guest size and SHA256 agreement, terminal-state verification and
process-absence checks. This reclaimed 8,315,666,432 bytes; Windows then had
46,907,797,504 bytes free. The full Mac result, checkpoints, native restart
backups, logs and inputs remain intact. Receipt:
`validation/guest_result_archive_20261106.json`. The active CF320 solver was
unaffected. Recheck actual growth/capacity before later 320/640 cases.

### Independent early-surface diagnosis (November 5, 19:42 EST)

Six independent two-second calculations now separate early mesh/time effects.
They are **not native ANSYS results** and never enter the serial native queue.
All finish with zero removed rows and no material-scope crossing; maximum energy
and mass residuals are 8.20e-12 and 6.77e-16. Six shared native surface samples
from the 160/320 schedules agree within 0.000683 K. Full configurations, source
hashes and archived producer/model/configuration files are pinned in
`validation/early_surface_resolution.json`.

At 1.24375 s, reducing dt from 0.003125 to 0.0001953125 s at 160 rows changes
surface temperature by only 0.08103 K; reducing dt from 0.0015625 to the same
smaller step at 320 rows changes it by 0.17818 K. The common-step 160-to-320
mesh difference remains 166.06864 K. At that same step, 640 rows give
1261.27988 C; 1280 rows with a further quarter-step give 1280.05801 C.
The last 18.77812 K difference is a joint mesh/time change, not isolated mesh
error. Full hot-face history convergence remains unestablished. The row's
available-char mass and conversion enter the coupled consumption/energy cap;
these tests identify predominant mesh sensitivity, not one uniquely isolated
term or a validated continuum ablation law. They are not lifetime calculations.

The short diagnostic worker has finished. Do not duplicate it from a stale PID.
Its exact source is archived by hash under `validation/source_archive`; the
ignored original is `ansystmp/heartbeat_checks/check_early_surface_resolution.py`.
The updated report includes the paired-step table and early heating curves.
The native queue, sealed input packages and thresholds are unchanged.

## Previous corrected-geometry queue record (November 5, 15:40 UTC)

The following record is historical; active runtime and counts are superseded above.

Booster CF 160/40 rows completed 300 s / 6976 accepted intervals. The full
native/log/restart validation was repeated and exactly reproduced the queue's
accepted record. All 22 independently compared checkpoint hashes were rechecked;
maximum sampled native/reference profile difference is 0.002837761 K. The
row-removal event at 3.696875 s and transfer at 3.700000 s match exactly within
the unchanged time tolerance. Cooling and persistent topology checks pass.

Its sampled inner/outer casing peaks are 117.739676/108.226601 C at
101.4375/143.4375 s, with 6.3103125 mm of retained mesh. Relative to the older
80/20-row quarter-step result, peak changes are 3.814404/3.360498 K and the
thickness change is 0.0396875 mm. These meet the 5 K and 0.0635 mm targets.
The comparison also changes sector geometry/measures and nonlinear tolerance;
it does not isolate radial error or establish hot-face convergence or lifetime.
All 6976 full fields were checked: maximum same-radius ranges are
1.0300e-5 K in phenolic and 1.13472e-4 K in the casing. The native log has
zero errors; its 21.9999998 C table-endpoint and generic elapsed-time/SMP
warnings do not alter the accepted result or establish an execution-mode speedup.

The unchanged observer **93981** advanced normally at 15:39 UTC to
`sustainer_al_pulse7_midpoint_joint320_geom005_smp10`. It now runs five remaining
resolution cases from `configs/campaign_queue.json`, serially with ten SMP cores.
The five sensitivity/cutoff controls stay deferred. All four 160/40-row cases
now have accepted terminal records, but sustainer CF's 10.714% scope-time change
still fails its five-percent target. Complete the queued 320/640-row checks.
Keep watcher 82419 and keep-awake 86412; never resume superseded observers.

Storage planning is recorded under ignored
`ansystmp/heartbeat_checks/native_storage_planning_20261105.json`.
Linear estimates from completed result sizes are 8.34 GB per full-horizon
320-row sustainer, 13.83 GB per 320-row booster and 33.37 GB for the 640-row
sustainer. These are planning estimates, not guaranteed bounds. Archive verified
completed guest results at terminal milestones and recheck actual growth before
each successor, especially the 640-row case; do not assume an earlier CF scope
stop. The existing 400 GB Mac / 10 GB Windows limits remain authoritative.

At 15:46 UTC, the completed booster CF160 guest `file.rth` duplicate was removed
after checking the full Mac copy and both guest-visible hashes/sizes, terminal
state and absence of any process using that runtime. This reclaimed
3,473,735,680 bytes; Windows then had 48,018,059,264 bytes free. All checkpoints,
restart files, logs, inputs and the Mac result remain intact. The receipt is
`validation/guest_result_archive_20261105_1546.json`. The active 320-row solver
was unaffected.

## Previous corrected-geometry queue record (November 5, 10:35 UTC)

The following paragraphs preserve the state at 10:35 UTC. The active case and
remaining counts are superseded by the later records above.

Booster Al 160/40 rows completed 300 s / 6976 accepted intervals. The terminal
native/log/restart audit was repeated and matches the queue's acceptance record;
all 22 independently compared checkpoint hashes were rechecked. Maximum sampled
native/reference profile difference is 0.002837762 K. Its one row-removal event
is scheduled at 3.696875 s and transferred at 3.700000 s; exact event timing,
persistent topology and the cooling transition pass. All 6976 full temperature
fields were inspected: maximum same-radius phenolic/casing ranges are
1.2002e-8/6.1107e-13 K.

Inner/outer sampled casing peaks are 87.271392/87.252119 C at
141.25/141.4375 s. The completed case retains 6.3103125 mm of mesh. Relative to
the older 80/20-row quarter-step case, peaks change by at most 2.711210 K and
retained thickness by 0.0396875 mm, below the respective 5 K and 0.0635 mm
targets. This pair also changes sector geometry/measures and solver tolerance;
it does not isolate radial-mesh error or establish a calibrated lifetime.

Observer **93981** advanced normally to
`booster_cf_pulse7_midpoint_space160_geom005_smp10` at 10:23 UTC. Six resolution
cases including that active run remain, followed by five deferred controls.
There is still one serial queue with ten SMP cores per solve. The earlier
launch recovery below is historical; no new recovery or input change occurred.

Sustainer CF 160/40 rows reached its provisional 150 C casing-property flag at
31.25 s (2676 intervals); full native/log/restart and independent audits pass.
Its accepted scope bracket is [31.1875, 31.25] s, with inner/outer endpoint
temperatures 150.057710/107.919866 C and 4.70296875 mm retained mesh. The prior
80-row quarter-step bracket is [34.9375, 35] s. This 10.714% scope-time change
fails the five-percent refinement target despite unchanged retained thickness.
The pair also changes geometry measures/angle and nonlinear tolerance, so it
does not isolate radial-mesh error. The queued 320/640-row comparisons remain
necessary. The 150 C flag is a material-model limit, not casing failure or
liner burnthrough. All 2676 full fields were checked: maximum same-radius
variation is 1.402e-5 K in phenolic and 1.391e-4 K in the casing.

The old observer 73021 stopped after successful booster Al preflight because
Parallels guest-exec returned `Invalid argument` while requesting its first
transient launch. No solver/launcher, matching launch receipt, initialized
state or native `file.*` existed on either side when checked. The failed
intent and old log are preserved in `validation/native_queue_recovery_20261105.json`.
An explicit recovery launched one new serial observer, **93981**, using the
same sealed inputs. The native booster Al run is active with `-smp -np 10`.
The current log is `ansystmp/geometry_resolution_recovery_queue.log`;
`baseline_queue.pid` points to this observer. No failed simulation was retried
and no superseded sealed package was regenerated.

The sustainer Al geometry control COMPLETED 127 s / 4208 accepted intervals.
The old observer 38695 exited normally. Full native/log/restart validation and
the terminal independent comparison pass, including both exact removal events,
cooling, persistent topology, conversion and mass. Maximum sampled profile
difference is 0.003588553 K. `validation/native_geometry_control_terminal.json`
pins the accepted record and comparison hashes. Inner/outer sampled casing peaks
are 122.245423/122.224915 C at 78.125/78.25 s; 4.70296875 mm of mesh remains.
Relative to the older 80-row quarter-step case, casing peaks shift by at most
2.468894 K and retained thickness is unchanged, but the 7 s hot face changes
1422.375972 to 1438.802077 C (+16.426106 K). This is a combined radial-mesh,
geometry-measure and solver-tolerance comparison, not isolated spatial or
surface-temperature convergence. No burnthrough or calibrated lifetime follows.

The single current observer is **93981**. It runs the six remaining cases in
`configs/campaign_queue.json` serially, currently
`booster_cf_pulse7_midpoint_space160_geom005_smp10`, ten SMP cores per solve.
Never restart the superseded observers 73021, 38695, 54373 or 22032.
The storage watcher 82419 and keep-awake 86412 remain active.

Thirteen fresh successor packages were prepared and checked after the sustainer
Al terminal review. Two of those (sustainer CF and booster Al) have since
completed; six resolution cases and five deferred sensitivity/cutoff controls
remain. Geometry is 0.05 degrees with exact straight-sided measures; native
heat-flow tolerance is 1e-7. Every parent is preserved. Radial/axial divisions,
time schedules, physical inputs, controller, material DLL and removal gates
match the corresponding parent. Direct face/volume integration passes for all
four configurations and all prepared resolutions. The new mappings and hashes
are in `validation/native_geometry_successor_plan.json`; the old one-core to
ten-core lineage stays intact under `execution_successors`, and geometry
successors have a separate mapping. All four matching narrow-sector STEP files
now pass two-body round-trip checks; original STEP files remain unchanged.

The main diagnostic hold has been archived, not silently discarded. No extra
native default cases were added. In particular, the later cutoff control's
comparison with its older default native case also changes geometry/tolerance;
its own independent reference verifies implementation, while the pair cannot
isolate cutoff effects alone. The five controls remain deferred until this
resolution queue finishes and is reviewed. Each terminal case still requires
all native and independent gates before the queue advances.

### Full-field check after the geometry control

The November 5 03:35 UTC continuation checked all 4,208 accepted three-dimensional
temperature fields of the completed sustainer Al geometry control. The largest
same-radius axial/angular range is 1.3584e-8 K in the live phenolic and 1.0516e-12 K
in the casing. Radial averaging therefore conceals no appreciable numerical
temperature variation in this uniform aluminium control. This is not a check of
real-motor hot spots, end effects or carbon-fibre orientation in the pending cases.
The checkpoint digest and extrema are in
`validation/native_uniformity_sustainer_al_pulse7_midpoint_space160_geom005_smp10.json`.

`model/check_native_uniformity.py --runtime <terminal runtime>` now writes a
separate record for each completed refinement, preserving the original primary
four-case record. It checks sealed inputs and checkpoint indices/times, and
refuses a runtime without terminal acceptance. The original sustainer Al summary
was reproduced exactly. Apply this check to subsequent accepted refinements,
particularly the CF cases, before the final refined-field interpretation.
At that milestone the reviewed 74-page PDF was the completed-control edition
from commit `1ffb4544`. The later 75-page CF-refinement report is published in
`dc442e0d`; the diagnostics below do not change its reported temperatures.

The November 5 05:36 UTC check also inspected all 20,896 accepted fields from
the four completed quarter-step cases. Maximum same-radius phenolic/casing
ranges are 1.2063e-8/1.1369e-12 K (sustainer Al), 0.006516/0.012962 K
(sustainer CF), 1.0811e-8/4.5475e-13 K (booster Al), and 0.005749/0.010385 K
(booster CF). Each runtime has a separate `native_uniformity_<runtime>.json`
record with sealed-input, accepted-record and ordered-checkpoint hashes. The
booster CF check includes its preserved one-core prefix and ten-core successor.
These small within-radius variations support the use of radial averages for
these uniform-sector numerical comparisons. They do not resolve the 10.714%
CF scope-time refinement failure or validate real-motor circumferential
uniformity. The active booster Al 160/40-row run was not included in this
terminal-only check.

### Additional verified guest-result archiving (November 5, 11:11 UTC)

Reclaimed a further 4,789,633,024 Windows bytes from the completed
`sustainer_cf_pulse7_midpoint_space160_geom005_smp10` and
`booster_al_pulse7_midpoint_space160_geom005_smp10` runs. Only their redundant
guest `file.rth` files were removed. The full Mac copies were read and hashed;
Windows then independently hashed both the local and shared copies, checked
equal sizes, terminal status/index and absence of a process using each target,
and rechecked terminal state/process absence immediately before removal.
Inputs, checkpoints, restart backups and logs remain intact. The two receipts
and hashes are in `validation/guest_result_archive_20261105_1111.json`.

Afterward Windows had 47,737,995,264 bytes free and the Mac had
1,494,104,092,672 bytes free. The same booster CF solver and observer 93981
continue; no queue, sealed input, result interpretation or report changed.
Continue checking available capacity as the 320/640-row cases run.

### Verified guest-result archiving (November 5, 04:39 UTC)

Reclaimed 5,560,205,312 bytes from Windows by removing only the redundant
`file.rth` files in these completed Iris runtimes:

- `sustainer_al_pulse7_midpoint_space160_geom005_smp10`
- `booster_al_pulse7_midpoint_time_quarter`
- `booster_cf_pulse7_midpoint_time_quarter_smp10`

Each full native result remains in the corresponding Mac `ansystmp/runs/`
directory. The Mac copy was read and hashed; Windows then independently checked
its byte count and SHA256, terminal index/status, and absence of a solver using
that runtime immediately before removing its duplicate. The archive record is
`validation/guest_result_archive_20261105.json`. No input, checkpoint, restart
backup, log, rejected diagnostic, active-run file or queued package was removed.
Windows had 48,146,452,480 free bytes after this operation; the active CF run
continues to consume storage. Recheck capacity after each completed refinement,
and archive further completed result duplicates only with equivalent checks.
The existing 10 GB guest and 400 GB Mac stop limits remain unchanged.

The sections below preserve the diagnostic history. Their old PIDs and dispatch
instructions are historical and do not describe the active queue above.

## Historical geometry-consistency control and handoff

The November 5 03:05 UTC continuation is finishing this control. The independent
check through 109.0625 s still passes all gates, with the same maximum sampled
profile difference. No terminal acceptance is inferred from this prefix.
`model/prepare_geometry_successors.py` now supports a guarded handoff:

1. After the single observer exits successfully, run `review` with the study
   Python environment. It repeats the full native/log/restart validation,
   checks runtime-specific independent evidence and records the completed
   control and mixed numerical comparison in `native_geometry_control_terminal.json`.
2. Inspect that result, then run `prepare`. It reuses the verified control and
   creates thirteen fresh sibling input packages (eight remaining resolution
   cases and five deferred controls), preserving every sealed parent. Exact
   geometry integration and unchanged material/controller/driver checks apply.
3. Run `activate` only after preparation review. It requires no native solver
   or old queue observer, then updates the campaign and validation mappings.
   It does not launch anything. Explicitly launch the resulting eight-case
   `current_dispatch` once, serially, on ten SMP cores. Five controls remain deferred.
4. Generate the remaining three matching 0.05-degree STEP files using `geometry.py
   --config` with representative new cases; preserve the existing sustainer Al
   control STEP. Build/review/publish the completed-control report edition.

The offline guard record `validation/native_geometry_successor_guard.json`
checks thirteen prospective configurations and verifies that attempting
preparation while the control is running stops before any input or campaign
write. The plan is not a launch authorization for a parallel solver. The report
generator can now consume a verified terminal-control record; absent that record,
it continues to show the earlier frozen prefix. No current result was changed
by preparing these handoff/report routines.

The frozen prefix in `validation/native_geometry_control_prefix.json` now passes
both exact row-event comparisons and the cooling transition through index 2541,
22.8125 s. `model/freeze_geometry_control_prefix.py` verified every native interval,
all sealed inputs and all 17 sampled checkpoint hashes before freezing this record.
The maximum sampled live-profile difference is 0.003588553 K at 7 s; it is not a
bound over every intermediate state. Native maximum relative energy residual is
7.9940413e-5, hot-power residual 5.7196813e-8 and absolute mass residual
7.7368472e-22 kg. Both event sets agree: row one at index 1114 / 3.48125 s,
row two at index 2094 / 6.54375 s; subsequent transfer times are 3.484375 and
6.546875 s. The largest native/reference event-time difference is 1.56e-13 s,
below the unchanged 1e-8 s check. Persistent topology and cooling controls pass.

This is PREFIX verification only. No terminal acceptance record exists yet;
the prescribed 127 s cooling run and full native/restart/spatial reviews remain.
Observer 38695 still runs only this control. Keep the main dispatch held until
terminal review; do not launch remaining old packages or a second solver.
The English report now records the geometry equations, failed older event checks,
the joint nature of the correction, current event table and sampled profile plots.
Its four primary/time-only result sets and complete source appendix are retained.

The November 5 02:38 UTC continuation additionally checked the independent
reference through index 3274 / 68.625 s. All event, cooling, field and topology
gates still pass; the maximum sampled profile difference remains 0.003588553 K.
This later routine check is ignored runtime evidence, not a new report edition.

Before remapping the control into the resolution plan, retain the new
configuration-comparison metadata in `model/compare_native_resolution.py`.
The old 80-row quarter-step to new 160-row pair also changes sector angle,
area/volume convention and heat-flow tolerance; it is a **combined numerical
comparison**, not an isolated radial-mesh check. The later corrected 160/320/640
pairs must retain common geometry measures and solver tolerances so that their
joint mesh/time differences can be interpreted. The comparator now records these
changes and refuses a convergence pass if physical inputs or removal controls
differ. It accepts runtime-specific comparison evidence for a terminal diagnostic
without rewriting that diagnostic's sealed role. A running prefix is excluded.
The report generator labels mixed pairs explicitly when they become available.
`validation/native_resolution_configuration_guard.json` verifies that all eight
existing terminal summaries and four time-only outcomes remain unchanged, checks
five deliberate physical-model mismatches and four numerical classifications,
and confirms that the active control is still absent from terminal comparisons.
No campaign mapping, native input or running solver changed in this continuation.

The tighter heat-flow tolerance did NOT resolve the second-row discrepancy.
`sustainer_al_pulse7_midpoint_space160_tol1e7_smp10` schedules row two at
6.540625 s versus 6.543750 s independently, just as the 1e-5 parent did.
Its native balance, persistent topology, one-substep and cooling-transition
checks pass. The independent live-profile difference is at most 0.199085 K
through the inspected 16.3125 s prefix, but the strict event gate fails.
Observer 22032 was stopped; the run paused cleanly at index 2453 / 17.3125 s,
with full paused native/input/restart audits and zero remaining solver processes
verified before any replacement launch. See `validation/native_tolerance_diagnostic_outcome.json`.
Neither paused 160-row runtime is an accepted full convergence pair.

The ONLY current dispatch is
`sustainer_al_pulse7_midpoint_space160_geom005_smp10`, observer PID **38695**.
The new preflight and launch succeeded, with `-smp -np 10`. Its log is
`ansystmp/geometry_control_queue.log`; `baseline_queue.pid` and
`geometry_control_queue.pid` identify this single observer. The storage watcher
and keep-awake remain active. No other native case may launch alongside it.
The original main dispatch and all old sealed inputs remain preserved and held.

This is a fresh run from 22 C, not a restart of either discrepant history.
It keeps 160/40 radial cells, two angular and two axial cells (800 solid elements,
1809 nodes), 0.5 mm height, the original radial dimensions, reaction/material
laws, time increments, 1e-7 heat-flow tolerance, removal cutoff and all gates.
The total sector angle changes from 0.5 to 0.05 degrees. Controller measures use
actual straight-sided faces/volumes: face width 2*r*sin(dtheta/2), and element
volume 0.5*(r_outer^2-r_inner^2)*sin(dtheta)*height. The new configuration opts
into `mesh_measure_convention=straight_sided_hex`; historical configurations
retain `cylindrical_arc`. Regenerating the maps in memory for all four archived
primary configurations yields exact dictionary equality; no archived package
was rewritten. Direct triangle and hexahedral integration of the new deck gives
area ratios within 3.3e-13 of unity and volume ratios within 1.1e-10.

`validation/native_geometry_control_plan.json` records the verified geometry,
input hashes and unchanged material/controller/driver logic. The script
`model/prepare_geometry_control.py` prepares only fresh inputs and refuses an
existing target; it does not launch a solver. Because exact measures and sector
width change together, this is a JOINT geometry-consistency/angular refinement
control; do not separately attribute their effects. Full-ring scaling changes
from 720 to 7200 to match the reduced angle. The independent cylindrical
reference equations remain unchanged; its continuous-sector integration is
still a distinct numerical representation.

The initial 39 intervals through 0.121875 s passed native audits and the independent
comparison (maximum profile difference 0.00012031 K). Native hot-power mismatch
is now at most 5.20e-8 in that prefix, consistent with exported-field precision.
That early check did not cover row events; the newer prefix above now does. A matching
curved two-body STEP, `geometry/sustainer_al_sector_0p05deg.step`, was exported
and reimported; its volumes and dimensions pass the independent round-trip checks
in `geometry/sustainer_al_0p05deg_validation.json`. Original STEP files are intact.
The CAD arc volumes are deliberately distinguished from polygonal FE volumes.

Both row events and the pulse-to-cooling transition have now passed. Complete the
full terminal/native restart audit; a passing partial history alone is not success.
If the strict comparison fails again, pause cleanly and investigate; do not
retune the cutoff or relax gates. If it passes, review the final geometry/spatial
comparison before mapping remaining cases to fresh corrected packages. None of
the remaining old sealed 0.5-degree packages has been regenerated or launched.
The older sections below are historical evidence, not the active dispatch.

## Diagnostic hold (November 4, 23:11 UTC)

The serial observer PID 54373 was deliberately stopped after a strict second-row
scheduling disagreement in `sustainer_al_pulse7_midpoint_space160_smp10`.
The native run paused cleanly at index 2814 / 39.875 s; all native balance,
substep, input-hash and restart audits passed. No guest solver remained at that
pause confirmation; the later diagnostic below is a fresh calculation.
The same-mesh independent field checks pass (maximum profile difference
0.244620 K), but native row two schedules at 6.540625 s versus 6.543750 s
independently. This one-step difference FAILS the exact scheduling gate.
It is not an accepted full convergence pair. Published primary and time-only
results remain unchanged. See `validation/native_row_schedule_issue_space160.json`
and ignored `ansystmp/heartbeat_checks/row_schedule_diagnosis.json`.

`configs/campaign_queue.json` records `dispatch_hold`. Do not resume the stopped
observer or the paused case, regenerate sealed inputs, or relax the event gate.
The current geometry-consistency control above is the only active dispatch;
main-campaign recovery requires reviewing its event and terminal gates.
Keep ten cores per solve and one serial queue. The storage watcher remains active. The dispatch
section below describes the preserved pre-hold lineage, not a running observer.

## Preserved precision diagnostic (launched November 4, 23:16 UTC; now paused)

Former observer PID 22032 ran only
`sustainer_al_pulse7_midpoint_space160_tol1e7_smp10`, freshly started from 22 C.
Its preflight passed and the native command/log confirm `-smp -np 10` and one
process with ten threads. The paired ANSYS261 launcher and ANSYS executable
are one calculation, not two cases. The heat-flow convergence setting is
1e-7 versus 1e-5 in the paused parent. Mesh (160/40), exposure, material DLL,
controller, time increments and acceptance gates are unchanged; driver/wrapper
paths point to the new folder. Horizon remains 127 s. Source and input identity
checks are in `validation/native_tolerance_diagnostic_plan.json`.

The main campaign's `dispatch_hold` remains in force. Before its pause, this
observer was recorded in `ansystmp/baseline_queue.pid` and
`ansystmp/tolerance_diagnostic_queue.pid`; its log is
`ansystmp/tolerance_diagnostic_queue.log`. Do not start another queue or solver.
No original convergence mapping has been replaced by an unverified diagnostic.
Inspect both removal events (around 3.48 and 6.54 s), the cooling transition,
full native audits and exact independent scheduling before accepting it.
If a repeated mismatch appears, pause cleanly again and investigate its cause;
do not adjust the removal threshold to make event times agree.

Offline replay through index 2100 reproduces native mean conversion to within
2.97e-8. At index 2093, the second-row residual is 0.000522960 of initial row
mass natively and 0.001095126 independently, straddling the unchanged 0.001
cutoff. Consumed fractions differ by 0.000572169; the difference in conversion
is only about 6.5e-9 there. Thus accumulated char consumption, rather than the
mean-versus-weighted conversion at that endpoint, dominates this event mismatch.
The source of that consumption difference remains under investigation; tighter
solver precision is a testable hypothesis, not an established explanation.
`model/check_row_schedule_diagnosis.py` preserves the native prefix hash,
reaction replay, residual/consumption fractions and live-row flux reconstruction.
Its data are diagnostic, not accepted spatial convergence results.

The comparison gate now checks both event time equality and the complete set of
row events, in addition to sampled layer counts. Previously, a late native event
could evade the count-only check because both models had removed the row by the
native endpoint. Regression tests reject either sign of a one-interval mismatch.
All nine saved passing comparisons retain matching event times; no accepted
result required withdrawal. See `validation/comparison_event_gate_regression.json`.
The comparison utility is outside the sealed native solver package; the live
physical calculation and its native acceptance rules remain unchanged.

The latest reviewed PDF and its primary/time-only results are unchanged. This
failure/recovery milestone updates operational evidence, not motor predictions.

## Geometry-measure diagnosis (November 5, 00:12 UTC)

The tighter-tolerance run has passed the first row transfer and the independent
comparison through 5.121875 s (maximum live-profile difference 0.094607 K).
Its second event is still pending; do not call the precision hypothesis resolved.

Independent work found a separate geometric inconsistency. The mesh generator
stores curved-sector arc areas and volumes in the controller map, while the
SOLID278 coordinates describe straight-sided faces. Direct triangle areas and
2x2x2 hexahedral Jacobian integration confirm, for the 0.25-degree angular cells:

- actual face / controller area = 0.9999992067256581;
- actual element / controller volume = 0.9999968269048979.

The actual native hot-power ratio follows the face-area factor: its mean
residual from that factor is -1.12e-9, maximum absolute residual 5.92e-8 across
all 2240 heating steps of the paused 160-row parent. This distinguishes the
geometric discrepancy from ordinary exported-field precision. The existing
heat-power tolerance permits it; passing that audit is not exact geometry identity.

A controlled independent diagnostic reduces only assembled hot convection by
the chord/arc face-area factor, retaining the original controller removal sink.
That alone moves the second event from 6.543750 to 6.540625 s. The temperature
comparison still differs by 0.1593 K at 7 s, so this is not a complete native
reproduction or an accepted correction. No material parameter was fitted and
no acceptance gate was changed. The exact sector geometry audit and isolated
test are reproducible with `model/check_sector_geometry_measures.py`; compact
evidence is `validation/sector_geometry_measure_diagnosis.json`.

The precision trial subsequently failed its second-event check. The proposed
fresh control with mesh-consistent measures and a narrower sector is now the
active run described above. It preserves the radial mesh, time increments,
reaction/material laws and exact-event gate. The isolated perturbation here
remains diagnostic evidence, not a replacement independent reference or an
accepted convergence pair. The forthcoming report revision must explain the
geometry-measure distinction and whichever native controls actually verify it.

## Preserved ten-core dispatch before the diagnostic hold (November 4, 21:36 UTC)

The user explicitly requested ten ANSYS cores. The current production command is
`-smp -np 10`: one shared-memory solve with ten threads, one serial case queue.
Do not create concurrent motor solves or resume the superseded one-core queue.
The old observer PID 26648 was deliberately stopped at an accepted pause. The
replacement observer PID 54373 uses `--wait-resume-first`; always check the current
ignored PID file and process command rather than relying on these historical IDs.
The storage watcher remains PID 82419 with its existing keep-awake process.

Runtime active before the hold: `sustainer_al_pulse7_midpoint_space160_smp10`.
The preceding `booster_cf_pulse7_midpoint_time_quarter_smp10` completed at
21:32:04 UTC and passed full native and independent gates. It inherits the
immutable prefix through index 1117 / 3.490625 s from its one-core parent, whose
paused native/controller state remains intact. `restart_lineage.json` records
prefix and native restart hashes. Its live controller identity is the successor
configuration; copied historical checkpoints retain their original identity.
Full terminal validation verifies that lineage as well as all existing gates.

`verify_parallel_restart.py` compares 32 resumed steps against the separately
completed `booster_cf_core_restart_reference1`: maximum nodal difference
1.13687e-12 K, identical conversion, mass and energy integrals. All paired audits
pass. The native log and live process command confirm ten SMP threads/cores.
The same-mesh independent check through 3.996875 s also passes (0.00394 K maximum
profile difference). This is checkpoint/core repeatability, not completed
convergence, a speed benchmark, or verification of a row event during that short
comparison. Continue the full existing acceptance gates.

`current_dispatch` contains the ten `_smp10` successors attached to the observer;
its first case has completed, leaving nine spatial/joint cases. Four
sensitivity and one cutoff successor remain deferred. The original dispatch is
preserved under `superseded_dispatch_one_core`, and `execution_successors` maps
each name. Do not regenerate any sealed package. Physics, material DLL, geometry,
time steps and acceptance tolerances are byte-identical to each parent; only
execution configuration and launcher support changed. A failed first Parallels
launch request was verified not to have launched before one explicit reissue;
`parallel_resume_launch_retry.json` preserves this evidence.

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

## Material correction and accepted results before the core transition

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
and then completed sustainer CF quarter-step at 12:21:48 UTC and booster Al
quarter-step at 16:49:11 UTC. Booster CF quarter-step completed and passed both
gates at 21:32:04 UTC. Sustainer Al 160/40 is now active. No queue or solver was
duplicated. Nine native resolution cases remain, followed later
by the five prepared
sensitivity/cutoff controls below. The first quarter-step run passed all 4,208
accepted intervals through 127 s, removal/cooling controls and the independent
comparison (maximum profile difference 0.09913 K). Its first native time-only
comparison changes casing peaks by 0.721 K with unchanged retained mesh;
this does not establish native spatial convergence.

Historical observer PID 26648 began at 06:57:11 UTC with the dispatch below;
it was superseded during the verified core change. The ONLY current serial
observer is PID 54373 (verify baseline_queue.pid and the actual command):

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

The current_dispatch field records the ten-case ten-core dispatch, with the first
case now complete. The original sixteen-job continuation is historical provenance. Primary
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
It now has eight completed records and four passing time comparisons: the four
primaries and all four quarter-step cases. Sustainer Al inner/outer casing peak changes are
-0.72076/-0.72055 K, with unchanged retained mesh. Sustainer CF has 2,736 accepted
single-substep intervals through its property-scope stop at 35 s, bracketed by
34.9375--35 s. Inner/outer endpoint casing temperatures are 150.01301/114.83103 C,
with 4.70296875 mm retained. Its scope time changes 2.941 percent from the
primary 34 s result; this passes the stated timing target without establishing
spatial convergence. The maximum same-mesh independent profile discrepancy is
0.099122 K; exact row scheduling, persistent removal and cooling controls pass.
Maximum native step energy residual is 0.033686 percent. Warnings repeat USERCK,
elapsed/CPU performance and the negligible 21.9999998 C KXX-table undershoot;
the controller property-scope guard remained active.

Booster Al quarter-step passed all 6,976 native intervals through 300 s. Its
independent maximum profile discrepancy is 0.067557 K; exact row scheduling,
persistent topology and cooling controls pass. Maximum native step energy
residual is 0.061479 percent, and hot-load relative error is 8.517e-7.
Inner/outer casing peaks are 84.56018 C at 142.6875 s and 84.54176 C at 142.875 s.
Their changes from the primary are -0.22368/-0.22359 K, with 6.270625 mm retained
in both cases. The first row schedules at 4.584375 s and load transfers at
4.5875 s. Nine spatial/joint refinement cases remain; sustainer Al 160/40 is active.
These are conditional numerical results, not material failure or lifetime predictions.

Booster CF quarter-step passed all 6,976 intervals through 300 s, including
1,117 immutable inherited one-core steps and the accepted ten-core continuation.
The parent-prefix hashes, sealed successor, native logs and latest native restart
backup all passed validation. Independent maximum profile discrepancy is
0.0675564 K; exact row scheduling, persistent removal and cooling checks pass.
Maximum step energy residual is 0.061479 percent and hot-load relative error
8.5273e-7. Inner/outer casing peaks are 113.925272 C at 102.875 s and
104.866103 C at 144.1875 s. Their changes from the primary are
-0.317896/-0.264732 K, with unchanged 6.270625 mm retained. The first row
schedules at 4.584375 s; load transfer follows at 4.5875 s. The hot face at
7 s is 1419.617559 C and its sampled peak is 1487.194041 C. These remain
conditional numerical values, not a real firing or lifetime prediction.

Its logs retain USERCK, the negligible initial CF-table undershoot and elapsed/CPU
performance warnings. The resume also reports two absent temporary control files
during initial deletion; both are regenerated by the normal controller before
use. A generic advisory recommends DMP after the ten-core SMP session. Neither
log has native errors. This advisory is not a measured speed comparison; continue
the verified user-requested ten-core SMP queue without changing sealed inputs.

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
  Compare with the completed sustainer_cf_pulse7_midpoint_time_quarter default
  case at identical time/mesh settings; the different horizons do not affect
  a shared earlier material-scope stop. This tests implementation, not the
  physical correctness of the tighter cutoff.

The campaign records deferred_sensitivity_runtimes and deferred_cutoff_runtimes.
Dispatch them only after the current serial queue exits and review permits it;
never create a second observer or native solver. All use the existing native
and independent acceptance gates. Keep runtime-specific comparison files.

## Remaining substantive work

1. Complete the four remaining queued native spatial/joint checks. Preserve the strict
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
The completed CF quarter-step comparison gives the same surface differences
to the shown precision: 1466.032 to 1422.376 C at 7 s, with a 48.688 K maximum
matched heating-history difference.
Both booster quarter-step cases similarly change the 7 s hot face from 1452.137 C
to 1419.618 C, while its sampled peak is 1487.194 C. The largest matched
heating-history difference is 63.089 K at 4.6 s, near the row-transfer event.
`native_hot_surface_time_comparison.json` reports all accepted time pairs
separately. Continue to
assess hot-face histories and row-transfer times during refinement; a passing
casing-target comparison does not establish hot-surface time convergence.

A 30-minute heartbeat, `iris-ansys-study-and-english-reports`, continues the
study. Notify only meaningful progress, failures, completion or necessary user
action. Keep it active while substantive work remains; stop on completion or
latched storage stop. Leave this file accurate for the next continuation.

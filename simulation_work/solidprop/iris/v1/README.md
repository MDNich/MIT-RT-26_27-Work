# Iris exploratory ANSYS study

**Current numerical hold (November 5, 00:40 UTC):** both 160-row trials (heat-flow tolerances 1e-5 and 1e-7) fail the exact second-row removal comparison. Both are cleanly paused and preserved. One fresh ten-core control now uses a 0.05-degree sector and mesh-consistent areas/volumes. Its removal and cooling checks are pending. The main campaign remains held; published primary/time-only results are unchanged. See `OPERATIONS.md`.

English-only autonomous study, authorized November 3, 2026. Read the parent
`AGENTS.md` and `phenolic_burnthrough_plan.md` for user requirements and physics.

Current execution: **one native case at a time, with ten shared-memory cores**
(`-smp -np 10`), as requested on November 4. The booster CF quarter-step
case was cleanly paused at index 1117 / 3.490625 s and resumed in a fresh sealed
`_smp10` package. Thirty-two resumed steps agree with a one-core native reference:
maximum nodal temperature difference 1.14e-12 K; conversion, mass and integrated
energy are identical. The native log confirms ten threads/cores. This short
verification covers heating before row deletion; all subsequent topology,
cooling, balance and independent-reference gates remain required.

Ten continuing resolution cases and five deferred controls received ten-core
successor inputs. Booster CF quarter-step has now completed its full 300 s
horizon; nine resolution cases remain. The sustainer Al 160/40-row refinement
is paused for the strict event mismatch described above; a separate single-case
geometry-consistency diagnostic is running. `configs/campaign_queue.json` records their names and the single
current observer. Prior one-core results, inputs and checkpoint lineage are
preserved. The printed primary source appendix describes those original primary
runs; the execution change is documented separately in the report and
`validation/parallel_restart_comparison.json`. Ten requested cores do not establish
a measured speedup; serial coupling and file transfers still contribute runtime.

Current status: four 0.1 s native pilots and all four analytical conduction
benchmarks passed. The native conduction error was below 0.013 K. The sustainer Al
and CF, and booster Al/CF seven-second baselines are complete with 560 accepted
steps each. All four same-mesh native/independent profile checks passed.
The controlled restart exactly matches the uninterrupted reference; the native
pulse/cooling control also passed. Sixteen manufactured native layer-removal
states verify live elements and moving hot-face loads, including the final
exposed-casing state, within 0.00048 K of the analytical cylinder.
Nine native prescribed-temperature reaction checks also passed, with maximum
conversion error 1.72e-8 against the analytical first-order law.
The first refined run exposed a restart defect: an already removed layer returned
because ANSYS does not retain element-deactivation commands across multiframe
restart. The 10.42% energy error stopped the calculation at attempted 4.175 s;
that step is rejected. A native four-case regression verified the correction
against uninterrupted solves exactly. Fresh `_restartfix` packages replay all
removed layers, check native live counts, and preserve accepted native restart
copies. The corrected run completed its seven-second heating segment, but cooling was
withdrawn after ANSYS internally subdivided the first cooling interval in a way
the endpoint energy audit did not support. New packages require one native
substep per accepted controller interval. Paired default/tight solver controls
have completed. They identified separate nonlinear-tolerance and inherited
reaction-temperature errors: the old routine used endpoint temperature plus half
the increment, rather than the intended midpoint. A rebuilt library subtracts
half the increment, passed six native temperature-change checks and a corrected
motor pilot (0.00124 K independent profile difference). Fresh corrected midpoint
80/20-row cases use tighter heat-flow convergence. Corrected sustainer Al is
complete through 127 s with 1,052 accepted single-substep intervals. Its full
native audit and same-mesh independent comparison pass (maximum profile
difference 0.3334 K), including identical first-row removal and cooling transfer.
The prescribed seven-second heating pulse leaves 4.7030 mm of retained mesh;
the sampled inner-casing maximum is 120.50 C at 79 s. These are exploratory
80-row results, not a demonstrated motor lifetime or completed mesh convergence.
Corrected sustainer CF has also reached an audited terminal point: the
provisional 150 C material-property flag at 34 s during cooling. It retains
4.7030 mm of mesh, and the independent comparison passes within 0.3335 K.
That is a model-scope stop, not casing failure or liner burnthrough. Corrected
booster Al is complete through 300 s with 1,744 accepted single-substep intervals.
Its independent comparison passes within 0.2205 K; 6.270625 mm of mesh remains.
Its sampled inner/outer casing peaks are 84.7839/84.7654 C at 142.75 s.
Booster CF is also complete through 300 s: the native audit and independent
comparison pass (maximum profile difference 0.2205 K), with 6.270625 mm retained.
Its sampled inner peak is 114.2432 C at 102.75 s; the outer peak is 105.1308 C
at 144.25 s. All four corrected primary cases have now reached audited terminal
states: three completed horizons and the sustainer CF scope stop. The thirteen-case
native time/mesh campaign remains unfinished and is currently held for the
event-timing investigation described above. The sustainer Al
quarter-step case is complete through 127 s and passed both audits: its inner
casing peak shifts by -0.721 K and retained mesh thickness is unchanged. This
time comparison does not establish spatial convergence. Sustainer CF quarter-step
has now passed 2,736 native intervals and its independent check through the
150 C property-scope stop at 35 s (bracket 34.9375--35 s), a 2.941 percent
change from the primary 34 s stop. Retained mesh is unchanged; the largest
same-mesh profile difference is 0.09913 K. Booster Al quarter-step has also
passed all 6,976 intervals through 300 s and its independent check (maximum
profile difference 0.06756 K). Its inner/outer casing peaks are 84.5602/84.5418 C,
changing by only 0.224 K, with unchanged retained mesh. Booster CF quarter-step
has also passed all 6,976 intervals through 300 s, including its preserved
one-to-ten-core restart lineage and the independent check (0.06756 K maximum
profile difference). Its inner/outer casing peaks are 113.9253/104.8661 C at
102.875/144.1875 s, changes of -0.31790/-0.26473 K; 6.270625 mm remains.
All four time-only comparisons now meet the casing/scope and retained-thickness
targets. Nine spatial/joint refinement cases remain; sustainer Al 160/40 is active.
The hot-face differences remain significant: both boosters change by 32.520 K
at 7 s and up to 63.089 K at matched times near row transfer. The report adds
all four matched hot-face difference curves, keeping this separate from casing
convergence. These primary cases retain the documented
0.1-percent removal rule; completed histories do not establish native mesh
convergence. Each terminal run must pass both
native audits and independent field, row-schedule and control checks before
the queue advances. No second queue or solver may be started.
Historical native curves retain their original routine and are explicitly labelled. See the ordered list
in `configs/campaign_queue.json` and ignored `ansystmp/baseline_queue.log`.

The independent radial checks show that 20 phenolic rows do not resolve
recession. Long-duration exhaustion diagnostics also fail mesh/time-step
convergence and exceed the provisional casing property range. Those results
are explicitly rejected as lifetime predictions. New physically interpreted
long-exposure calculations stop at the property-range flag (150 C CF, 300 C
Al); these are model-scope limits, not certified structural failure criteria.
No credible motor burnthrough time has yet been established.

The intermediate English report includes accepted casing
temperatures, solid/gas/char mass bookkeeping, independent/native profiles,
refined property-scope stopping points and 54 independent input sensitivities.
These sensitivities are engineering scenarios, not measured confidence bounds.
Source archives and compact verification records are under `validation/`.
Independent pulse/cooling refinement captured delayed casing heating; the
booster native cooling horizons have been extended to 300 s in fresh sealed
packages. Finer surface-coupling time checks resolved the two strongest-heating numerical
comparisons through 640 cells; agreement in event timing alone had concealed
thickness error. Eight hypothetical 20/60-second pulse refinements also passed.
Twelve independent capacity-only diagnostics also quantify retained-cell storage
sensitivity; they are not a conservative removal model or physical error bound.
These independent results remain exploratory. Native resolution packages
separate time-step changes at 80 rows from 160/320-row spatial refinement,
with an additional 640-row sustainer CF case. Their plan and completed-pair
summary are validation/native_resolution_plan.json and
validation/native_resolution_comparison.json; prepared cases are not results.

Eight combined-input pulse scenarios have completed independent 80/160/320-cell
refinement; all final comparisons pass (casing maxima <0.86 K, retained thickness
<0.020 mm). These combine the existing engineering perturbations and are not
confidence bounds or proven worst cases. Four bounded native sensitivity
controls are prepared but deferred until the active queue finishes.

The row-removal cutoff is now an explicit limitation. Twenty-four paired
independent calculations found -7.21 to +16.12 percent changes in sustainer CF
scope time when the nominal 0.1-percent residual-solid rule is varied. Another
24 calculations at tighter cutoffs and 320/640 cells pass their final successive
numerical comparisons; two additional CF cutoff decades still shift timing by
about 1.4-1.5 percent each. A zero-cutoff limit is not physical validation:
first-order conversion leaves a positive unreacted fraction at finite reaction
exposure, so finite residual ejection needs a modelling rule or calibration.
Existing native cases retain their sealed rule and their times remain conditional
on it. A separate native CF cutoff control is prepared for later confirmation.

The four original exact two-body STEP sectors are in `geometry/`. The new
0.05-degree sustainer Al control has a separate matching, round-trip-checked
`geometry/sustainer_al_sector_0p05deg.step`; original geometries are preserved. The English report is
`output/pdf/iris_phenolic_report.pdf`; accepted data and figures are in
`docs/analysis/`. Independent radial data live in `validation/radial/` and
are explicitly distinguished from native ANSYS states. Native output and
checkpoints are under ignored `ansystmp/runs/`, with some jobs executing in
`C:\IrisStudy\runs` and mirroring accepted state to the Mac. The original
studies remain unchanged.

## Detailed physics, code and temperature interpretation

The expanded report now derives the pyrolysis update, mixture law, gas release
and sensible-energy sink, blowing correction, pressure-dependent char law,
available-energy/char caps, finite-element weak form and time discretization.
It documents the actual density/enthalpy basis, incomplete constitutive tangent,
lagged surface coupling, row-removal cutoff and retained partial-cell capacity.
These limitations are not hidden by a passing mass/energy audit.

The gas is prescribed at **2504 K (2230.85 C)** during the hypothetical seven-second
pulse. The accepted 80/20-row hot phenolic surface reaches **1480-1488 C**;
at 7 s it is **1452-1466 C**, while the casing interface is only **22-30 C**.
Later 85-150 C casing values and cooler final hot-face values describe different
locations or times. These are exploratory native results, not converged/calibrated
surface-temperature predictions. The new heating-only figures and radial profiles
make the distinctions explicit. The attached September report is a historical
comparison with different geometries and model variants, not a same-case benchmark.

The PDF prints the complete corrected Fortran routine, material block, MAPDL
transient/resume/export scripts, surface controller, build commands and a complete
representative mesh deck. Exact small input copies for **all four primary cases**
are in `docs/analysis/source_listings/`; `source_manifest.json` records their hashes
against the sealed, audited runtimes. The CF material/orientation excerpt has
original deck line numbers. Copies and listings do not launch or modify a solver.

The maintained explanatory source is `docs/en/thermochemical_details.tex`.
`docs/analysis/technical_details.py` generates the temperature comparison and
source appendix as part of the normal report build. The report must be rebuilt,
rendered and visually reviewed after edits; do not edit only the generated PDF.

The host Python environment is in ignored `ansystmp/venv`. Windows ANSYS v261
and its Python 3.10 interpreter execute the native analysis. Large output stays
under ignored `ansystmp`; Git contains reproducible inputs and compact reports.

Storage controls are implemented in `model/ops.py`. Run `check` before work and
keep `watch` active throughout solver activity. `STOP_WORK.json` is a latched
stop requiring review; never bypass it. A check failure must stop launches and
report generation. The Mac floor is 400 GB decimal; Windows C: floor is 10 GB.

`model/publish.py` commits reviewed Iris-only milestones and optionally pushes
to main. It rejects staged files and newly reachable Git objects >=100 MB.
Invoke only after the milestone's validation and report visual inspection.

Planned sequence: exact STEP sectors, input register and small meshes; native
license/DLL pilot and validation; English setup report; four baseline cases;
convergence and sensitivity cases; interim reports; final comparison. Actual
firing duration and heat flux are unknown, so all exposure schedules are
explicit scenarios, not reconstructed flight histories.

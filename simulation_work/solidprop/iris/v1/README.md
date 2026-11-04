# Iris exploratory ANSYS study

English-only autonomous study, authorized November 3, 2026. Read the parent
`AGENTS.md` and `phenolic_burnthrough_plan.md` for user requirements and physics.

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
states: three completed horizons and the sustainer CF scope stop. Thirteen
native time/mesh checks continue in the existing serial queue; the sustainer Al
quarter-step case is active. These primary cases retain the documented
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

Four exact two-body STEP sectors are in `geometry/`. The English report is
`output/pdf/iris_phenolic_report.pdf`; accepted data and figures are in
`docs/analysis/`. Independent radial data live in `validation/radial/` and
are explicitly distinguished from native ANSYS states. Native output and
checkpoints are under ignored `ansystmp/runs/`, with some jobs executing in
`C:\IrisStudy\runs` and mirroring accepted state to the Mac. The original
studies remain unchanged.

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

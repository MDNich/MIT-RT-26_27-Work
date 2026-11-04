# Iris exploratory ANSYS study

English-only autonomous study, authorized November 3, 2026. Read the parent
`AGENTS.md` and `phenolic_burnthrough_plan.md` for user requirements and physics.

Current status: four 0.1 s native pilots and all four analytical conduction
benchmarks passed. The native conduction error was below 0.013 K. The sustainer Al
seven-second baseline is complete with 560 accepted steps; its checkpoint
pause/resume has advanced.
A serial queue will complete the four 20-row baselines, restart/pulse controls,
and four refined seven-second pulse/cooling cases with 80 phenolic rows and
20 casing rows. See the ordered list
in `configs/campaign_queue.json` and ignored `ansystmp/baseline_queue.log`.

The independent radial checks show that 20 phenolic rows do not resolve
recession. Long-duration exhaustion diagnostics also fail mesh/time-step
convergence and exceed the provisional casing property range. Those results
are explicitly rejected as lifetime predictions. New physically interpreted
long-exposure calculations stop at the property-range flag (150 C CF, 300 C
Al); these are model-scope limits, not certified structural failure criteria.
No credible motor burnthrough time has yet been established.

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

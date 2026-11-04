# Iris exploratory ANSYS study

English-only autonomous study, authorized November 3, 2026. Read the parent
`AGENTS.md` and `phenolic_burnthrough_plan.md` for user requirements and physics.

Current status: all four 0.1 s native ANSYS pilots completed on November 3,
2026. Each has eight accepted coupling steps, closed mass balance, and passed
the energy and applied hot-face power gates. These are execution checks;
burnthrough time and mesh/time-step convergence are not yet established.

Four exact two-body STEP sectors are in `geometry/`. The English setup and
results report is `output/pdf/iris_phenolic_report.pdf`; its compact accepted
data snapshot and figures are in `docs/analysis/`. Numerical validation records
are in `validation/`. The corrected pilot runtimes have suffix `_pilot2`;
the first Al pilot is retained locally as troubleshooting provenance.

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

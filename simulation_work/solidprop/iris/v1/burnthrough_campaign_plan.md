# Continuous-heating burnthrough campaign

User direction, November 5, 2026 (New York time): move beyond seven seconds,
choose exposure duration freely, prioritize answering when the phenolic is
burned through, and propose improvements to the simulated model. This replaces
the previous priority of completing every seven-second pulse refinement first.
Earlier accepted results remain available as regression evidence.

## Whole-wall verification milestone, November 5 at 22:33 EST

The second spatial discretization now carries nodal liner and backing mass and
enthalpy from ignition to the final moving-surface event. Its four refined
endpoints agree with the finite-volume model within 0.073 s. Native setup now
covers both backings throughout exposure with no prescribed casing temperature
or empirical time-to-event input. The two short native pilots precede the four
whole-wall exposures. The full-field output reader must independently reconstruct
the applied loads, heat balance, material histories and terminal event before
any native lifetime comparison is eligible. The active CF320 control and the
earlier native prerequisites retain their original sequence. See the current
operations record for the sealed inputs and the completed Windows preflight.

## Verified scope and remaining native work, November 5 at 22:08 EST

All eight independent CF calculations and their restart, mass, open-system
enthalpy and event audits are complete. The 17-page report gives the four
evolving-backing estimates, including earlier aluminium fusion and CF
property-range events. The native CF320 prefix passed at 6.33906 s; wait
for its terminal, restart and cooling receipts before launching the native
sequence described in OPERATIONS.md. The six CF terminal-window decks use
the very small residual virgin inventory at the 1000 °C crossing to justify
a pure-char approximation for the last section only. Their imposed backing
temperature comes from the independent histories. Full native verification
from ignition, including independent casing response, is still required.

## CF backing verification and continuous cases, November 5 at 21:50 EST

A separate eight-case independent campaign now couples the two competing
T700/M21 reaction channels to temperature, mass loss, gas enthalpy and radial
conductivity in each casing cell. It holds the dimensions fixed and vents
generated backing gas locally at its formation temperature. Liner gases still
enter the inherited blowing law. Resin conversion, the original 150 °C flag,
the 1000 °C literature ceiling and exhaustion each have separate event records.
The fine runs use 640 liner and 160 casing cells. Compare 320 versus 640 at
0.04 s, then 0.04 versus 0.02 s at 640, then the alternative catalyst at 0.02 s.
The scope is a literature surrogate under sustained heating. A two-cell coupon
first checked the coupling against an independently integrated temperature-form
ODE. Each refinement must pass its own record, source, mass and energy checks
before publication. Native dispatch remains gated by the existing CF320 run.

## Progress on November 5 at 21:27 EST

The conservative moving-face radial model, its manufactured checks, and the
20 nominal, 42 one-factor and 16 endpoint integrations are complete. The
[report](output/pdf/iris_continuous_heating_progress.pdf) gives conditional
exhaustion times for all four liners and shows when each casing exceeds its
property evidence. Ten further calculations now track aluminium fusion under fixed backing geometry.
A separate one-way T700/M21 diagnostic checks resin conversion on the archived
CF temperatures. The remaining work includes native comparisons, coupled CF
heat and gas balances, and high-temperature transport sensitivity. The current
CF320 verification remains the only authorized active native case.

## Question and deliverable

For each of sustainer Al, sustainer CF, booster Al and booster CF, determine a
conditional time interval for exhaustion of the continuous liner under a stated
sustained heating environment. Report surface position, remaining physical
thickness, retained virgin/char mass, temperature profiles and balances versus
time. The requested event is exposure of the casing, not conversion to char,
the first hot casing, or completion of an arbitrarily prescribed pulse.

Distinguish three outputs throughout:

1. A numerically verified event of a specified model under specified inputs.
2. Sensitivity of that event to the exposure, material and recession assumptions.
3. The part of the history supported by available material evidence. Record
   casing-property crossings and any modelled casing damage separately. A
   result after that crossing can be a hypothetical liner calculation, but
   cannot establish survival of the assembled motor.

The goal is a defensible conditional estimate or range, not a claim of measured
flight lifetime. Missing firing inputs do not justify returning to seven-second
survival as the main answer. They do require explicit load scenarios and a
clear statement of what would change when measured inputs arrive.

## Execution now

- The already-running CF320 native verification is left intact, with ten SMP
  cores. The old multi-case observer was replaced by an observer for that case
  only. Its terminal, native restart, same-mesh reference, row-transfer and
  cooling checks must still run. Receipt: `validation/burnthrough_priority_transition.json`.
- Three unstarted pulse refinements are deferred. The five previous bounded
  sensitivity/cutoff controls are also deferred until their relevance to the
  continuous-heating model has been assessed. Do not resume the old queue.
- A separate serial independent worker starts fresh continuous-heating scouts
  for all four motors. These do not consume another ANSYS license or launch a
  second native solve. The worker has a process lock, source/configuration
  fingerprints, storage checks and resumable state checkpoints.
- Nominal loading initially retains the inherited 2504 K gas, 1000 W/(m2 K)
  uncorrected convection coefficient, 800 psi pressure and documented blowing
  correction. Heating never turns off at seven seconds. First reporting
  milestones are 30, 60, 120, 240, 480 and 960 seconds, reached in one continuous
  integration. Stop earlier at an exhaustion event or numerical failure.
- A 960-second scout without an event is a censored calculation. Inspect the
  remaining mass, recession rate, energy budget and limiting mechanism before
  extending a fresh recorded horizon; do not invent an event or silently stop
  the study at this planning horizon.

The first scouts use 160 phenolic and 40 casing cells with a 0.0015625 s step
ceiling. They are a cost-effective search for the relevant time scale, not the
final mesh. All four configurations and code hashes are frozen in
`configs/continuous_heating_campaign.json`. Accepted equation balances alone
do not establish mesh convergence or physical validity.

`configs/continuous_heating_refinement.json` prepares eight subsequent checks:
for each case, 160/40 cells at half step, then 320/80 cells at that same smaller
step. Compare scout versus half-step to isolate time error, then the two meshes
at identical step to isolate spatial changes. The refinement runner requires
the scout completion receipt and acquires the same worker lock. Neither these
scouts nor their refinements relax the numerical or material promotion gates.

## Material scope in a long calculation

The first scouts deliberately record rather than stop at the existing 150 C CF
and 300 C Al property-range flags. This is a **new mathematical continuation**
with the explicitly retained casing surrogate, not acceptance of the earlier
rejected endurance studies or permission to treat surrogate properties as
high-temperature measurements. Those earlier results remain rejected.

No post-scope event may appear in an accepted physical-results table. Its
provisional label is `MODEL_EXHAUSTION_UNVALIDATED`. First fix numerical
dependence and then test the thermal backing assumptions against a supported
high-temperature material model. If casing integrity is lost before liner
exhaustion, give that ordering and retain any subsequent hypothetical intact-
backing result only as a conditional comparison.

## Improve the model in this order

### 1. Replace row-threshold recession with a conservative moving surface

The current finite row stays thermally active after some char mass has been
consumed, then disappears at a residual-mass threshold. Its surface char supply
depends on the current cell's mass and mean conversion. The measured early
surface mesh sensitivity and removal-cutoff sensitivity make this unsuitable
as an unexamined lifetime mechanism.

Develop a separate candidate using an explicitly moving radial boundary and
conservative control volumes or an ALE/remeshed thermal discretization. Advance
surface position from a surface mass balance and update the occupied volume,
conductive path and stored energy continuously. Remapping must conserve solid
mass, species/progress variables and enthalpy. A nearly empty numerical cell
must not retain its original heat capacity.

The first component is implemented separately in `model/moving_surface_remap.py`.
It integrates conserved fields in the exact cylindrical volume coordinate
`x = r^2/2`, reports the mass/enthalpy swept out of the domain and localizes a
prescribed-speed final event. `validation/moving_surface_remap_verification.json`
records analytic nonuniform remapping, zero-motion and prescribed pure-char
front tests at three resolutions. This is a verified geometry kernel only;
the coupled reaction/energy equations and a physical front-speed closure are
not yet implemented. The artificial 100-second benchmark is not a motor result.

Do not simply set recession speed equal to char flux divided by virgin density.
At a partially pyrolysed surface, relate front speed to virgin and char mass
crossing the moving boundary and to surface pyrolysis/gas release. A pure-char
front approximation is a separate assumption whose validity needs checking.
Reaching alpha=1 does not remove the char, and lowering a deletion cutoff to
zero is not a substitute for this surface mass balance.

### 2. Close the energy and surface coupling consistently

Write the open-system enthalpy balance before implementing it. Account for
remaining solid enthalpy, pyrolysis reaction energy, gas enthalpy transport,
surface reaction energy and enthalpy carried out with removed solid. Define
reference states and mass bases so a term is neither omitted nor counted twice.
Verify the total integrated balance including remapping and a final-cell event.

Iterate surface temperature, gas blowing, char consumption, boundary power and
conduction together within the time step. Compare to the lagged coupling using
fixed-mesh time refinements. Use adaptive steps governed by reaction progress,
recession fraction and temperature/energy error, with event localization as the
liner approaches zero thickness. A large solver step is acceptable only after
comparison against a refined solution, not merely because convergence occurs.

The candidate bulk and local wall balances are now implemented in
`model/moving_surface_thermochemistry.py` and `model/moving_surface_boundary.py`.
Their mass bases, enthalpy reference, reaction update, mixed-front assumptions,
and manufactured checks are derived in `docs/en/continuous_moving_balance.tex`.
Verification receipts are `validation/moving_surface_thermochemistry_verification.json`
and `validation/moving_surface_boundary_verification.json`. Next couple these
components to the time-dependent radial conduction and front motion, checking
the integrated balances at each accepted step and at final geometric exhaustion.
The local verifications do not establish a coupled motor result.

The radial conduction operator now passes a layered analytical resistance
test and independent time/space comparisons against a transient annular
eigenmode. See `validation/moving_surface_conduction_verification.json`.
A fresh 585-node, 256-element SOLID278 deck for that same inert annular mode is
sealed in `configs/native_verification/annular_mode64_smp10/`. The endpoint
and all nodal temperatures are prescribed as audit targets in `expected.json`.
Only inputs have been checked. Run this native verification on ten SMP cores
after CF320 has exited and its observer has completed the terminal audits.
Keep material laws and recession absent in this isolated conduction check.

A first transient finite-volume implementation now couples those components in
`model/moving_surface_transient.py`. It solves end temperatures, reaction,
surface recession, blowing and conduction together, then conservatively transfers
the reacted inventory over the swept cylindrical volume. All boundary product
fluxes use the same time-integrated surface area. Close each cell energy equation
and both cumulative ledgers. Merge a front remnant below half the design pitch;
preserve all unaffected interfaces and integrate the final contact time. The
manufactured zero-flux, exact pure-char recession and nonuniform mixed-coupon
checks and the checkpoint interruption test are recorded under `validation/`.

The sealed independent campaign `configs/moving_surface_campaign.json` runs
160/40 cells at 0.08 and 0.04 s, then 320/80 and 640/160 at 0.04 s and
640/160 at 0.02 s. Accepted steps may be smaller for reaction progress, surface
travel, output and the final event. Compare all prescribed shared times,
temperature profiles and left/right event brackets, including the initial
massless-face reconstruction. Keep these candidate results separate from the
previous finite-row study, native ANSYS, and physical motor-lifetime claims.

### 3. Give high-temperature backing a defensible meaning

For Al, obtain a documented alloy surrogate with temperature-dependent heat
capacity/conductivity, melting range and latent heat; keep unknown alloy/temper
explicit. For CF, distinguish fibres from the resin and provide a documented
decomposition/char surrogate rather than extending virgin cp indefinitely.
Map material axes as before. Neither thermal calculation by itself predicts
pressure-vessel integrity, delamination or a crack-driven early breach.

Until these data are implemented, compare clearly defined thermal backing
scenarios, such as the inherited surrogate and prescribed hot/cold interface
conditions. Treat these as sensitivity cases; do not assert mathematically
rigorous upper/lower lifetime bounds without proving monotonicity.

### 4. Resolve the uncertain imposed environment and consumption law

After numerical checks, repeat the lifetime calculation across the already
documented h, radiation, pressure/activity and effective removal-cost ranges.
Vary h and gas temperature separately and keep radiation/emission accounting
explicit. Chamber pressure and a stoichiometric propellant reaction alone do
not determine wall heat flux. Preserve gas-temperature versus wall-temperature
distinctions and record local liner exposure from ignition as an assumption.

Seek grade-specific thermogravimetric/DSC, conductivity, heat-capacity, char-yield
and recession measurements. Gas composition and finite-rate surface chemistry,
particle erosion, spallation, joints and debonding are potential improvements
whose data requirements must be stated. Do not add uncalibrated complexity just
to produce a precise time. The first priorities are conservation and the moving
surface; detailed pore-flow chemistry comes after those and after sensitivity
shows a reason to incur its cost.

## Verification and promotion gates

1. Reproduce accepted short-time fields and reaction checks with the inherited
   reference. Verify new campaign checkpoint/resume equality and final-event
   handling, with no duplicate independent worker.
2. For a candidate moving-boundary implementation, test zero heating/recession,
   cylindrical conduction, analytic reaction integration, prescribed constant
   recession, conservative remap of a nonuniform field, pure-char ablation and
   final-cell exposure. These are manufactured checks, not motor experiments.
3. Isolate time error at fixed mesh, then compare 160/320/640 radial cells with
   appropriate steps. Target less than 5 percent change in exhaustion time,
   agreement of event brackets, and remaining-thickness agreement within
   max(0.02 mm, 1 percent of initial thickness) at shared intermediate times.
   Assess hot-face profiles separately; previous casing-only passes are
   insufficient. If a target fails, diagnose before merely adding run time.
4. Require native versus independent agreement on shared physical assumptions,
   histories, integrated balances, recession and event brackets. A new moving
   surface formulation need not have identical intermediate row-kill timestamps
   to the old discretization; it does need its own verified event definition.
5. Prepare fresh native ANSYS input packages for the validated continuation or
   candidate formulation, then dispatch serially after the active case exits.
   Preserve the ten-core SMP setting, small sector, correct midpoint material,
   exact mesh measures and restart verification. Do not modify sealed inputs.
6. Publish separate native and independent evidence. Only promote a conditional
   burnout estimate after all relevant numerical gates pass. An estimate can
   remain material-uncalibrated; state that uncertainty explicitly rather than
   implying calibration from code-to-code agreement.

## Reports and operations

At meaningful milestones publish the setup, governing balances, discretization,
solver controls, model changes and results in English. Keep the complete MAPDL
and Fortran listings and comparison with the earlier formulation. Plot remaining
thickness versus time to the event, surface/inner/outer temperatures, conversion
profiles, mass/energy budgets, numerical convergence and input sensitivity. Mark
property-scope crossings and unvalidated extrapolation directly on the plots.

The next substantive deliverable is the four continuous scout outcomes plus
their limitations and a tested moving-surface/conservation candidate. It is not
another assertion that a seven-second pulse leaves most of the liner present.

The 400 GB Mac and 10 GB Windows floors, latched stop, verified-copy cleanup,
single native solver, no sub-agents, and no Git blobs >=100 MB remain unchanged.
Use `model/publish.py` for milestone pushes. Continue the existing heartbeat
under this revised priority; do not create a duplicate automation.

## Method references

- Chen and Milos, *Effects of Nonequilibrium Chemistry and Darcy-Forchheimer
  Pyrolysis Flow for Charring Ablator* (2013),
  https://ntrs.nasa.gov/citations/20130014432. The paper describes a moving-grid
  material-response model with energy, decomposition and surface balances. Its
  PICA/re-entry parameters are not Iris phenolic or motor calibration data.
- Clark, *An analysis of a charring ablator with thermal nonequilibrium,
  chemical kinetics, and mass transfer* (1973),
  https://ntrs.nasa.gov/citations/19730017234. A reference for separating
  pyrolysis, char thickness, surface recession and gas transport, with simplified
  exact-solution checks. It does not supply this motor's erosion coefficients.

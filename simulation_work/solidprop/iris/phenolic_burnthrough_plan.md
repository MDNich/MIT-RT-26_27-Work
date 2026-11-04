# Iris Phenolic Burnthrough Simulation Plan

Updated November 4, 2026. Scope: sustainer and booster, each with an aluminium or carbon-fibre composite casing. The Windows VM is running and the user has authorized autonomous implementation, exploratory simulations, English reports and milestone pushes to GitHub.

The calculation will answer **when the phenolic liner loses its remaining physical thickness under a specified motor firing history**. It will also report pyrolysis depth and casing temperatures, because the casing or its bond can exceed a thermal limit while char still remains. The starting point is the previous ANSYS MAPDL thermochemical model in `newmotor_phenolic_study/v0`, extended to the four Iris configurations.

The dimensions are sufficient to prepare the geometry. The user has confirmed that firing heat flux and duration are unavailable and has requested evidence-based assumptions and sensitivity ranges. Use 800 psi nominal pressure and the previous reports' gas temperature and phenolic/aluminium properties as the initial exploratory basis. CF thermal properties still need supported surrogate data. Results remain conditional on the imposed exposure and consumption law.

## Confirmed operating environment and user decisions

The following inventory was checked directly on November 3, 2026. Available disk and memory figures are snapshots, not reservations.

| Item | Observed state and execution decision |
| --- | --- |
| Host | MacBook Pro, arm64. Repository is `/Users/mdn/Developer/MIT-RT-26_27-Work`. |
| VM | Parallels `Windows 11 (1)`, UUID `{e7540578-be7d-4ee0-9a40-8aa94dcb9efd}`, running Windows 11 Pro ARM64, build 26200. |
| Resources | 14 virtual CPUs and about 112 GiB RAM; about 104 GiB guest memory was free. The user now requests ten shared-memory cores per native solve; retain one serial case queue. Original primary results used one core. Measure throughput separately from core count. |
| Solver | `C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe` and the underlying `ANSYS.exe` are present. Verify exact release and successful user-material loading in a native pilot. File presence alone is not a solve test. |
| Supporting tools | Workbench executable exists; bundled Python reports file version 3.10.19. Intel Classic Fortran 2023.1 is present at the historical path. Verify compiler/linker operation only if a DLL rebuild is needed. |
| License | Local TCP port 1055 responds and license processes exist. Port 2325 did not respond. Actual feature checkout, rather than either port alone, determines whether MAPDL can run. |
| Shared storage | `\\Mac\Home\Developer\MIT-RT-26_27-Work` is readable from Windows. The historical V: mapping is absent in the inspected automation session; create a dedicated mapping in the same execution identity as the solver. |
| Disk | Mac had about 1,513 GB free; Windows C: about 59.5 GiB. Use the Mac share for large files and measure shared-folder performance. |
| Existing calculation | No MAPDL/MPI solver processes appeared in the inspected process inventory. Recheck immediately before launching each job. |

The user requested small axial and sector slices, **at least five radial elements per material layer and ideally twenty**, rather than the previous very large mesh. The approximately 1.0 +/- 0.25 m fuel length is an inventory estimate only. Use twenty radial cells in each of the two material regions initially, then compare finer meshes where required for recession or thermal-gradient accuracy. A homogenized CF casing is the starting representation; individual fabric plies are not asserted without a supplied motor layup.

### Disk limits and publication

Before generation, launches, report builds, transfers and Git pushes, check free space on the Mac volume. Monitor that volume during active jobs. **Below 400,000,000,000 bytes free, stop all new work**, latch a storage-stop status, request a clean controller pause and issue a solver-controlled stop for an in-progress nonlinear solve. Do not continue report generation or automatically resume after the stop. Keep the last fully accepted state distinct from any interrupted solver state.

Independently keep Windows C: above **10,000,000,000 bytes free**. Account for scratch files and the next expected write burst before starting. Copy this study's inactive results to the Mac share, verify sizes and hashes, then remove only redundant guest copies if necessary. Do not delete earlier studies or unrelated files. A Mac-share write still consumes the Mac disk; moving files out of the VM does not waive the host limit.

Push each major completed milestone: setup, initial report, significant intermediate results, and final report. Before committing, check staged file sizes and reject anything at or above 100,000,000 bytes. Before pushing, check newly reachable Git blobs as well. Native solver/restart files, environment packages, scratch output and incomplete exports remain ignored. Reports, STEP inputs, generators, configurations, compact accepted data and provenance belong in Git.

## Implementation findings (November 3, 2026)

The four native 0.1 s pilots have passed, using MAPDL 2026 R1.02 and the
inherited user material. Four native constant-property conduction checks
agree with the analytical cylindrical solution within 0.013 K and verify the
CF axes. The setup and initial English report have been pushed to GitHub.

Independent 20/40/80/160-row calculations show that the initial 20-row
phenolic discretization is insufficient for recession. Keep the small slice
and refine phenolic radial resolution; the prepared native comparison uses
80 phenolic and 20 casing rows. This is a refinement justified by evidence,
not an assertion that 80 rows already establish lifetime convergence.

The independent assembly now explicitly uses the diagonal specific-heat
matrix employed by SOLID278 without advection. The old radial script used a
consistent matrix; it cannot be copied unchanged as an exact native transient
reference. Short-time comparisons with the corrected independent model are
within about 1 K at the hot face for the sustainer.

Long-exposure numerical stress tests leave the casing property range before
exhaustion and show substantial time/mesh dependence. Preserve them as rejected
diagnostics. Do not publish their apparent exhaustion times as burnthrough
predictions. Physically interpreted endurance/pulse studies stop at the first
provisional casing property-range crossing. Investigate partial-cell storage
and lagged surface coupling separately from missing material calibration.

## What counts as burnthrough

Pyrolysis converts virgin phenolic into gas and char. Fully pyrolysed material can still occupy the liner and insulate the case. Consequently, neither reaching a chosen temperature nor reaching conversion `alpha = 1` defines physical burnthrough.

| Quantity | Definition and reporting |
| --- | --- |
| Phenolic burnthrough time | First time the continuous phenolic barrier is exhausted at a modelled location. In the two-layer geometry, this exposes the casing. Report the interval between the last accepted intact state and the first accepted exhausted state. |
| Remaining physical thickness | Initial thickness minus actual surface recession. Retained char counts as remaining material. Record the minimum over locations, not only a spatial average. |
| Pyrolysis depth | Depth of the contiguous `alpha >= 0.98` front, retained for comparison with earlier work. Also save the conversion profile; this threshold is a diagnostic, not a removal rule. |
| Casing or bond thermal limit | First crossing of a specified material temperature or degradation criterion, plus peak inner/outer casing temperature and its time. Keep this separate from phenolic burnthrough. |

Use time since each motor's ignition, with local liner exposure time recorded separately. If the liner remains through the firing and the simulated cooling period, report **“burnthrough not reached through X seconds; minimum remaining thickness Y mm.”** A numerical failure is an incomplete run, not evidence of survival. A separate constant-exposure endurance study can estimate a hypothetical longer duration, but cannot replace the actual firing history.

This thermal recession model represents an intact liner. Cracks, joints, debonding, particle erosion and char spallation need additional evidence or modelling before the result can describe the earliest physical breach of a real motor.

## Four motor configurations

The following values are calculated from [motorspec.md][spec], using exactly 25.4 mm/in. The specification explicitly calls the propellant dimension a **radius**. For initial geometry preparation, assume it is also the phenolic inner radius, and interpret the phenolic and case dimensions as radial thicknesses. Confirm any grain-to-liner gap, inhibitor, adhesive or separate insulation before freezing the model.

| Case | Assumed liner inner radius, mm | Phenolic thickness, mm | Liner outer radius, mm | Case thickness, mm | Case outer radius, mm |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sustainer Al | 39.6875 | 4.7625 | 44.4500 | 3.1750 | 47.6250 |
| Sustainer CF | 39.6875 | 4.7625 | 44.4500 | 3.1750 | 47.6250 |
| Booster Al | 65.0875 | 6.3500 | 71.4375 | 4.7625 | 76.2000 |
| Booster CF | 65.0875 | 6.3500 | 71.4375 | 4.7625 | 76.2000 |

Independent diameter checks: sustainer bore / liner exterior / case exterior = **79.375 / 88.900 / 95.250 mm**; booster = **130.175 / 142.875 / 152.400 mm**. The booster shares the previous v0 model's outer interfaces but has a different bore and a thicker liner; the old geometry cannot be reused unchanged.

Within each Al/CF pair, hold geometry, phenolic properties and motor environment fixed to isolate the casing effect. Sustainer and booster receive their own firing histories. If the actual Al and CF motors have different operating conditions, add those as separate operational comparisons.

## What the previous work contributes

| Previous work | Use in this study |
| --- | --- |
| [Phenolic case study, Simulations 1 and 2][old-report] | Reuse the documented pyrolysis formulation and implementation lessons. Their nominal diameters were used as radii; their quantitative results are not an Iris geometry benchmark. |
| [Phenolic case study, Simulation 3][old-report] | Reuse the corrected thin-sector approach and checks on moving hot-face loads. At 7 s, virtual recession was 0.446254 mm while geometric removal was only 0.0396875 mm. These are different quantities; do not infer liner lifetime from either a conversion threshold or the virtual recession alone. |
| [New motor v0 report][v0-report], [configuration][v0-config], [controller][coupler] and [UserMatTh][usermat] | Primary implementation base: transient conduction, conversion-dependent properties, pyrolysis energy, gas cooling, blowing, separate char consumption, progressive row removal, accepted checkpoints and balance checks. |
| [October radial model][radial-model] | Use the independent cylindrical model to check radial conduction and screen sensitivities cheaply, after removing its hard-coded old geometry and loading. Agreement with ANSYS is numerical verification, not experimental calibration. |

The September 26 v0 [accepted snapshot][snapshot] ends at **6.375 s**, with **0.01984375 mm removed**, **4.74265625 mm remaining**, and a **0.59039 mm** 98% pyrolysis front. It demonstrates why conversion and removal must remain separate. The README contains an older 5.25 s snapshot; neither historical status is a statement about a currently running solver. The later radial comparison extends to 6.4125 s. Previous linear front projections and long-duration radial forecasts are not measured or validated burnthrough times.

## Material inputs

### Carbon fibre from the ACP tutorial

The attached [ACP tutorial][acp], page 4, defines a fabric composite with the following properties. Its material axes describe the fabric plane and thickness; they must be mapped to the motor casing rather than copied as global axes.

| Tutorial property | Value | Relevance |
| --- | --- | --- |
| Density | 1451 kg/m³ | Candidate casing density, subject to confirmation that the motor uses the same cured composite. |
| Elastic moduli X / Y / Z | 59.16 / 59.16 / 7.5 GPa | For a later structural analysis; not conductivity. |
| Thermal expansion X / Y / Z | 2.2e-6 / 2.2e-6 / 1.5e-5 K⁻¹ | For thermal strain; not heat transfer. |
| Thermal conductivity and specific heat | Not supplied for CF | Required for the transient thermal calculation. |

Page 3 gives **1.27 W/(m·K)** and **802 J/(kg·K)** for **G10**, not CF; those values must not populate the CF material. Pages 1 and 5 describe a fin layup of seven 0.009-inch plies per side with angles `0/0/45/0/45/0/0`. That is a fin construction, not the motor layup. Do not infer casing ply count by rounding the specified case thickness to this ply thickness.

The user directed reuse of the fin report and authorized surrogate assumptions for missing inputs. Use its density of 1451 kg/m³. Start the homogenized woven CF surrogate at 0.55 W/(m·K) radially and 2.5 W/(m·K) in both surface directions; published woven-composite measurements provide the corresponding 0.5–0.6 and 2–3 ranges. Use the virgin T700/M21 heat-capacity fit `cp = 2.8773 T + 687.31` J/(kg·K), with T in Celsius, as a separately identified material surrogate. Clamp this fit above 200 °C rather than silently extending it, and flag the resulting high-temperature approximation. A 150 °C casing-temperature flag marks the edge of the conservative property-evidence range; it is not an asserted resin failure temperature. Compare wider conductivity and heat-capacity ranges, including the NASA carbon-epoxy reference. These substitutions do not identify the user's actual resin/layup. [Woven-composite measurements][woven-cf]; [T700/M21 measurements][cf-fire]; [NASA thermal model][nasa-cf].

### Phenolic and aluminium

For regression checks, retain the v0 virgin/char property tables and reaction model: reference densities 1250/600 kg/m³, Arrhenius `A = 333 s⁻¹`, `Ea = 64081 J/mol`, order 1, and pyrolysis enthalpy 418 kJ/kg. These are inherited assumptions until checked against the Iris phenolic grade, reinforcement, cure and char yield. Identify the mass basis of reaction enthalpy and use it consistently in the material routine and energy audit.

The old aluminium constants are 2700 kg/m³, 167 W/(m·K), and 896 J/(kg·K). Use them only for reproducing the previous model. Production cases need the actual alloy and temperature-dependent properties. Any casing temperature limit must come from the alloy/temper condition or composite resin system; melting temperature or carbon-fibre strength alone is not a pressure-casing acceptance criterion.

## Heating history and exposure

Heat flux remains pending, and the user confirmed that no firing history is available. Track the following missing inputs for future updates; their absence does not block the authorized exploratory study:

| Input | Required definition |
| --- | --- |
| Firing history | Ignition, pressure versus time, burn duration, tailoff, and postburn gas/cooling conditions. State whether pressure is absolute. |
| Liner heat load | Time and axial dependence, units, uncertainty, and whether it is incident heat, net heat into the wall, or an estimate based on a specified wall temperature. |
| Gas-based alternative | Gas/recovery temperature and heat-transfer coefficient versus time/location; radiation treatment and relevant gas/particle environment. |
| Exposure geometry | Grain, port, inhibitor and bond arrangement, plus when each liner region becomes exposed. Propellant outer radius is not automatically the initial combustion-port radius. |
| Exterior and interfaces | Initial temperature, outside convection/radiation or surrounding structure, actual bond thickness and thermal contact resistance. |
| Surface consumption data | Measured recession or mass loss under representative conditions, or supported gas-composition/kinetic/erosion inputs. |

Apply one consistent hot-boundary formulation:

- **Measured or supplied net flux:** apply that flux to the exposed surface. Do not add convection, radiation, blowing or removal-energy deductions already included in its definition. Retain each internal reaction/transport term only if the supplied flux definition leaves it to the solid model.
- **Gas environment:** calculate convection from `h_eff(t) * (T_g(t) - T_surface)` and add radiation separately. Apply the previous blowing correction only to an uncorrected convective coefficient, with an explicit treatment of pyrolysis gas and any surface-reaction products.

Use the previous constant gas temperature of 2230.85 °C, coefficient of 1000 W/(m²·K), and exterior conditions as the initial **exploratory exposure**, with 800 psi nominal pressure now also supplied by the user. Retain 600–1000 psi as an inherited sensitivity range. Treat 800 psi as absolute for the reaction-rate calculation and record that convention. Test h = 500/1000/2000 W/(m²·K) and hot effective emissivity = 0/0.1/0.3 as deliberately broad engineering scenarios, not measured confidence bounds. The reaction in `motorspec.md` does not determine the wall flux or firing duration.

Check atom and mass balance of the supplied reaction and calculate its implied reactant/product mass bookkeeping. Combine the approximate 0.75–1.25 m fuel length with the specified outer radius to report a solid-cylinder envelope volume. Any mass estimate must state its assumed density, unknown port fraction, omitted binder and packing/void assumptions. Do not convert that inventory into a burn duration without a grain port and supported burn-rate law. Stoichiometric products alone are not an equilibrium combustion calculation; retain the inherited gas temperature rather than asserting an adiabatic temperature from the reaction line.

If grain shielding is unknown, a liner exposed from ignition can be a clearly labelled screening scenario. It is not an established exposure history or a guaranteed worst case for every failure mechanism. Model supplied axial variations with separate representative stations initially, then include axial conduction where needed.

## ANSYS model and implementation sequence

### 1 Prepare a reproducible four-case model

Create a new version under the Iris directory, with shared physics and four explicit configurations. Generalize the old aluminium-specific geometry/material fields and constant boundary conditions. Keep the earlier studies as references. Validate radii, layer thicknesses, volumes, material assignments and units analytically before meshing.

Continue with native MAPDL transient thermal analysis and the existing UserMatTh/controller approach. Use the known 2026 R1 toolchain initially, recording the exact solver and library versions; rebuild and recheck the user routine if the solver version changes. Prepare the native database and input deck, then run a no-solve preflight before any transient job.

### 2 Establish the radial reference and sector model

Begin with cylindrical radial conduction to check geometry, thermal resistance and transient storage. The production reference will use the previous **SOLID278 thin sector**, with explicitly meshed phenolic rows so consumption can move the hot surface. SOLID278 supports transient conduction and oriented orthotropic conductivity; the casing material axes require an explicit check. [ANSYS SOLID278 reference][solid278]

Use a **0.5° sector and 0.5 mm axial slice** for locally uniform loading. Two angular divisions, two axial divisions and twenty radial cells in each of the two materials give **160 elements and 369 nodes per initial model**. Map CF axes to the local tangent, motor axis and radial direction. Use adiabatic cut faces under these uniform-wall assumptions; verify slice independence with a wider/taller comparison. Scale integrated mass/power by sector angle; do not scale temperature, heat flux or recession. Whole-motor mass estimates remain separate from the slice analysis.

Represent the initial CF casing as an orthotropic homogeneous laminate surrogate with twenty radial cells. If actual layup data become available, compare its through-thickness resistance and areal heat capacity with a layered model before replacing the surrogate. Use ACP if helpful to inspect that layup; the fin tutorial's static-structural workflow is not itself a burnthrough solver.

Extend the domain for joints, closures, axial gradients or circumferential hot spots. A uniform sector predicts uniform-wall response and cannot establish a global minimum lifetime at an unmodelled local feature.

### 3 Restore and verify thermochemical coupling

Carry forward the phenolic conversion law, temperature-dependent virgin/char properties, endothermic pyrolysis and documented gas-energy treatment. Keep the approximation that released gas reaches the surface without resolving pore pressure explicit. Compare the regression case against the archived v0 history before changing material or load assumptions.

Surface recession needs its own calibrated law for char reaction and, where relevant, erosion/spallation. The v0 effective kinetic/mass-transfer law and 35 MJ/kg removal-energy cost are exploratory. Check reaction heat, availability limits and transport assumptions against the selected material/environment before treating this closure as predictive. Sensitivity studies with it remain conditional estimates.

Review the v0 treatment of partially consumed surface cells: the controller subtracts consumed char from its mass inventory while the live finite element retains its thermal material until row removal. Quantify the resulting storage/conduction error with radial refinement; if it materially changes lifetime, implement a consistent partial-cell or moving-boundary treatment before production runs. A closed bookkeeping mass balance alone does not resolve this approximation.

### 4 Implement removal and event detection

Use the v0 residual-solid-mass rule as the starting numerical criterion: schedule an exposed row for removal when less than 0.1% of its initial virgin mass remains. Test sensitivity to that tolerance. Preserve remaining char until the consumption law removes it; do not kill rows merely because conversion exceeds 0.98 or 0.99.

On every removal, clear old hot-face loads, identify the new exposed live faces, recompute area and reapply the boundary condition. Record expelled residual mass and energy. ANSYS element deactivation suppresses an element's thermal capacity and loads, so a successful solve alone does not demonstrate correct load transfer. [ANSYS EKILL reference][ekill]

Add an explicit final-row event before requesting another phenolic row. Record both scheduled exhaustion and actual topology removal; they can differ by a controller step. Bracket burnthrough and refine that interval rather than reporting an interpolated time as exact. A nonuniform model must track local surface columns instead of deleting a whole row on its mean mass.

### 5 Run firing and cooling histories

Run Sustainer Al, Sustainer CF, Booster Al and Booster CF with identical numerical settings within each pair. Begin with a 0.1 s native pilot, then a 7 s baseline for continuity with earlier work. Run explicitly hypothetical 7, 20 and 60 s heating pulses with cooling extensions, and a separately labelled continuous-exposure endurance branch. Extend the latter in reviewed intervals to a burnthrough event or a documented numerical/material-validity limit. These durations are scenarios, not estimated burn times. If burnthrough occurs first, retain its checkpoint; further heating of exposed casing requires an appropriate casing/bond degradation model.

Replace the old fixed 7 s horizon and step-count cap with each case's specified exposure. Do not hold firing conditions indefinitely just to obtain a finite crossing. If continued exposure is requested as an endurance scenario, clearly identify its imposed boundary conditions and stop when the material model leaves its supported range.

### 6 Establish uncertainty and physical validation

First vary heat-load history, phenolic properties, surface-consumption parameters, contact resistance, CF through-thickness conductivity/heat capacity, and initial thickness tolerance over supported ranges. Screen these cheaply with the radial model, then verify influential and combined adverse cases in ANSYS. Keep numerical convergence separate from uncertain physics, and do not assume the most conductive casing gives the longest liner lifetime.

Calibrate against representative recession, char depth, mass-loss and temperature measurements; reserve an independent exposure or specimen to check the prediction. Temperature agreement alone cannot validate material removal. Report an input-sensitivity envelope until enough data support a statistical interval. If erosion or spallation is important but uncharacterized, identify the result specifically as a thermal/chemical recession estimate.

## Numerical acceptance checks

These are proposed study targets, to be verified rather than treated as existing validation.

| Check | Planned acceptance |
| --- | --- |
| Simple thermal benchmarks | Recover cylindrical steady conduction and energy storage; with reactions disabled, match the radial reference. Check conductivity-axis orientation on a CF coupon. |
| Reaction and removal benchmarks | Check a uniform-temperature conversion history, zero-consumption case, imposed-recession case, first/last row removal, and restart across a removal. Verify load area and energy signs. |
| Radial resolution | Start with 20 radial cells in each material; compare 40 and 80. Phenolic pitches at 20 cells are 0.238125 mm for the sustainer and 0.3175 mm for the booster. At least 5 cells must remain the initial discretization minimum in each material layer; a disappearing liner naturally has fewer live rows near its end. Refine further only when convergence or partial-cell error requires it. |
| Time resolution | Start from the inherited 0.0125 s coupling step; compare with 0.00625 s and refine further near rapid conversion, load changes and burnthrough. Keep material-law parameters fixed. |
| Result convergence | Target less than 5% change in burnthrough time between the two finest runs, with a reported event bracket. If no crossing occurs, target agreement in remaining thickness within the larger of 0.02 mm or 1% of initial thickness; target casing peak agreement within 5 K. Tighten if a design decision lies within these tolerances. |
| Mass and energy | Retain the starting v0 gates: mass residual at most 1e-6 of initial liner mass, step energy residual at most 5%, and hot-load mismatch at most 2%. Also audit cumulative energy including gas, reaction terms and material removal. Investigate systematic drift and use absolute tolerances near zero power. |
| Solver outputs | Recheck the actual version's face heat-rate exports and user-source accounting. Preserve the previous independent reconstruction of pyrolysis/gas sinks where native outputs omit them; do not assume identical channel behaviour for a changed model. |

Measure pilot runtime and storage before committing to the full matrix. The previous 152,000-element model was expensive; reducing redundant axial/angular resolution must be justified by benchmark agreement. Use separate case directories, sealed input hashes, accepted checkpoints and complete restart partitions. Preserve errors and stop on failed audits rather than treating partially exported states as results.

## Deliverables and next implementation milestone

The first implementation milestone is a parameterized four-case geometry/material package, an input register distinguishing supplied data from inherited assumptions, a reproduced v0 regression case, and successful native preflights. Missing physical inputs are handled with the authorized exploratory scenarios and remain explicit in every report. Native preflight, solver convergence and experimental validation must retain separate statuses.

## Detailed unattended execution and reporting

### Step 1 Establish storage and execution identity

1. Check Mac free bytes and Windows C: free bytes, record both floors, and start the host disk watcher before launching a solver.
2. Register every active Iris runtime and its MAPDL job name so the watcher can request a clean stop for precisely this study's processes. A stale guard heartbeat also stops the next coupling step.
3. Use Parallels guest execution in a consistent identity and a dedicated I: mapping to the shared `iris/v1` folder. Do not rely on interactive-user V: mappings being visible to the automation account.
4. Check actual solver process names without accidentally treating `ansyslmd.exe` as a running calculation. Do not stop license services or unrelated applications.
5. Run a native one-element, no-solve probe. Record the release banner, license checkout, mesh inventory and warnings/errors. The November 3 probe passed with MAPDL 2026 R1.02; material-library loading still requires a solve.

### Step 2 Generate and verify geometry and input packages

1. Generate four named STEP files, each with exactly two solids, from the specified radii and the 0.5 mm/0.5° slice. The Al and CF geometries within each motor are dimensionally identical.
2. Reimport each exported STEP into an empty OpenCASCADE model and compare body count, cylindrical-sector volumes and axial bounds to independent formulas. Store dimensions, units, axis and validation results alongside the STEP files.
3. Generate conformal structured SOLID278 meshes from the same dimension record. STEP is the exchange geometry; the deterministic native mesh generator is the solver input route. Check that both describe the same solids.
4. Assign phenolic state variables and the appropriate casing properties. For CF, construct a local Cartesian material frame for every angular column and inspect the radial conductivity direction.
5. Keep source modules, material DLL, boundary definitions, geometry, mesh inventory and expected node/element counts in a sealed input package. Replace the old hard-coded 229,665/152,000 inventory checks with case-derived values.
6. Generate a distinct runtime for every pilot, mesh level and physical scenario. Never edit an already sealed or running configuration in place.

### Step 3 Verify the native solver and coupling

1. Preflight all four packages without time integration, rejecting missing material definitions, invalid element shapes and unexpected inventory.
2. Solve a short aluminium pilot to verify UserMatTh loading, nonzero conversion at heated points, thermal output extraction, body-source accounting and native heat-rate signs.
3. Solve the CF pilot and a conductivity-axis check. Verify that switching the casing changes only intended material properties, not exposed faces or heat-load area.
4. Run the historical-physics regression and an independent radial-conduction benchmark. For any disagreement, preserve evidence and fix the implementation before expanding the campaign.
5. Exercise first-row and last-row removal with controlled benchmark inputs. Check that hot-face power remains present after removal, residual mass is logged once, and the final event does not index a nonexistent row.
6. Compare a clean uninterrupted pilot with a checkpoint pause/resume. Check time, temperature, conversion, removed rows and mass/energy integrals. A solver restart without matching controller state is not accepted.
7. Use ten shared-memory cores (`-smp -np 10`) for continuing and remaining cases, following the explicit November 4 request. Keep one serial queue. The change from one core uses a separate sealed successor, matching accepted native/controller backups and immutable inherited checkpoints. Thirty-two paired resumed heating steps verified temperature agreement within 1.14e-12 K and identical conversion/mass/energy integrals. Keep the core count fixed within each successor execution; any further change requires its own preserved lineage and verification. Do not infer tenfold speedup from ten requested cores.

### Step 4 Complete the baseline and convergence matrix

1. Run the four 7 s baseline exposures with common step settings, preserving actual converged values at every accepted coupling time.
2. Compare 20, 40 and 80 radial cells per material and halved coupling steps. The small slice keeps these studies affordable; expand axial/angular resolution only for a demonstrated dependence.
3. Quantify the partial-consumption thermal-storage approximation and removal-thickness quantization. If it controls the answer, fix the material/removal representation or refine enough to bound its effect; do not equate a mass ledger check with physical accuracy.
4. Freeze the selected mesh/step settings only after the acceptance targets above are met, or report precisely why a target is unmet.
5. Run pulse/cooling cases and the separate continuous-exposure branch. Record model-range exceedance times independently of actual burnthrough and do not call arbitrary temperature flags structural failure.
6. Screen heat transfer, radiation, CF properties, pressure, phenolic properties and char-law multipliers, then confirm influential combinations natively. Preserve the distinction between parameter sensitivity and validated uncertainty.

### Step 5 Accept data and recover from interruptions

At each coupling step, compare observed solver time with the requested time, require every live element exactly once, ignore only already-dead surplus result rows, validate conversion bounds and close mass/energy audits. Commit the checkpoint atomically only after those checks. Figures and reports read accepted audits, never a still-exporting solver state.

For an unexpected exit, preserve logs and the complete failed directory, identify the last accepted controller state and matching native restart files, and work in a separate recovery directory. Diagnose the actual signature before selecting a recovery. Revalidate package identity and the first resumed step. Do not relaunch automatically from zero, mix unmatched native/controller states or weaken a balance tolerance to keep the campaign running. The explicitly verified one-to-ten-core successor transition is documented in v1/validation/parallel_restart_comparison.json. Routine faults are handled autonomously within this study; a storage-stop latch takes precedence over all recovery work.

### Step 6 Produce English reports and publish milestones

The report will have stable sections for purpose and assumptions, dimensions and STEP geometry, materials, heating and reaction physics, solver/coupler implementation, numerical verification, accepted results, sensitivities and conclusions. Use the previous LaTeX serif style, English labels, units on every axis, and solid sampled curves for computed results. Model extrapolations and hypothetical exposure branches must be visually distinct.

Create geometry/mesh figures first. Add temperature profiles and histories, remaining thickness, removed thickness, pyrolysis depth, gas/char mass histories, step/cumulative balance plots, convergence plots and four-case comparisons as the corresponding accepted data arrive. Include the source configuration hash, snapshot time/index and calculation status in each report edition. Never fill an uncomputed result with a fitted number.

Refresh at the end of each validation or baseline case, each meaningful endurance interval or sensitivity group, and approximately every 30 minutes when new accepted results materially change the report. Compile twice, inspect logs, render the PDF and visually check affected pages before publication. Keep the latest PDF stable in name and retain compact provenance for earlier snapshots. Avoid unnecessary copies of large images/results.

Commit and push the validated setup milestone, initial English report, meaningful intermediate reports and final report. The publishing helper checks the storage floors and the 100 MB file/blob limit. At completion, publish a comparison table, reproducibility instructions and all remaining limitations, then stop periodic monitoring. No claim of full pressure-casing qualification follows from this thermal study.

The final comparison will contain one row per motor configuration with:

- Burn duration and simulated end time; burnthrough bracket or “not reached.”
- Minimum remaining thickness at burnout and at the end of the simulated exposure.
- Pyrolysis depth and residual-thickness histories, with removal events identified.
- Peak liner/case interface and outside-case temperatures, times, and any supported thermal-limit crossings.
- Numerical resolution, input-sensitivity range and calibration status.

Archive native ANSYS inputs and material source, configuration hashes, accepted history CSVs, radial profiles, temperature/conversion plots and a concise comparison report. Large solver/restart files stay in ignored runtime directories. The headline answer will be **four conditional lifetime estimates or exposure-duration lower bounds**, with casing thermal limits alongside them.

## Source files

- [Iris motor specification][spec].
- [Previous phenolic report][old-report], especially geometry corrections and Simulations 2 and 3.
- [New motor v0 report][v0-report], [configuration][v0-config], [controller][coupler], [UserMatTh source][usermat] and [accepted snapshot][snapshot].
- [October cylindrical radial model][radial-model] and [comparison record][radial-validation].
- [ACP tutorial][acp], pages 1 and 3–7. It describes ANSYS 2024 R2 and a fin laminate.
- [ANSYS SOLID278 documentation][solid278] and [element deactivation documentation][ekill], checked November 3, 2026. Recheck behaviour against the installed solver during preflight.

[spec]: /Users/mdn/Developer/MIT-RT-26_27-Work/simulation_work/solidprop/iris/motorspec.md
[old-report]: /Users/mdn/Developer/MIT-RT-26_27-Work/simulation_work/solidprop/phenolic_case_study/docs/en/phenolic_pyrolysis_ablation_report.pdf
[v0-report]: /Users/mdn/Developer/MIT-RT-26_27-Work/simulation_work/solidprop/newmotor_phenolic_study/v0/docs/en/newmotor_phenolic_v0_report.pdf
[v0-config]: /Users/mdn/Developer/MIT-RT-26_27-Work/simulation_work/solidprop/newmotor_phenolic_study/v0/model/config.json
[coupler]: /Users/mdn/Developer/MIT-RT-26_27-Work/simulation_work/solidprop/newmotor_phenolic_study/v0/model/coupler.py
[usermat]: /Users/mdn/Developer/MIT-RT-26_27-Work/simulation_work/solidprop/newmotor_phenolic_study/v0/model/usermatth.F
[snapshot]: /Users/mdn/Developer/MIT-RT-26_27-Work/simulation_work/solidprop/newmotor_phenolic_study/v0/docs/analysis/accepted_results_snapshot.json
[radial-model]: /Users/mdn/Developer/MIT-RT-26_27-Work/simulation_work/solidprop/newmotor_phenolic_study/v0/docs/analysis/temperature_external_20261004/radial_model.py
[radial-validation]: /Users/mdn/Developer/MIT-RT-26_27-Work/simulation_work/solidprop/newmotor_phenolic_study/v0/docs/analysis/temperature_external_20261004/fit_validation.json
[acp]: /Users/mdn/Developer/MIT-RT-Simulation-Requests/tutorials/ansys/acp_fea/tutorial.ansys.ACP.fea.pdf
[solid278]: https://ansyshelp.ansys.com/public/views/secured/corp/v261/en/ans_elem/Hlp_E_SOLID278.html
[ekill]: https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/ans_cmd/Hlp_C_EKILL.html
[woven-cf]: https://www.researchgate.net/publication/288102626_Thermal_properties_of_carbon_fiber-epoxy_composites_with_different_fabric_weaves
[cf-fire]: https://pmc.ncbi.nlm.nih.gov/articles/PMC5459023/
[nasa-cf]: https://tfaws.nasa.gov/TFAWS12/Proceedings/TFAWS2012-AE-002.pdf

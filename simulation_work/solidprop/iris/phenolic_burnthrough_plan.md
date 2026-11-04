# Iris Phenolic Burnthrough Simulation Plan

Prepared November 3, 2026. Scope: sustainer and booster, each with an aluminium or carbon-fibre composite casing.

The calculation will answer **when the phenolic liner loses its remaining physical thickness under a specified motor firing history**. It will also report pyrolysis depth and casing temperatures, because the casing or its bond can exceed a thermal limit while char still remains. The starting point is the previous ANSYS MAPDL thermochemical model in `newmotor_phenolic_study/v0`, extended to the four Iris configurations.

The dimensions are sufficient to prepare the geometry. A predictive time still requires the firing heat load and duration, material data for the actual liner and casings, and a supported surface-consumption law. Until these are supplied, results using inherited properties will be labelled exploratory.

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

Obtain the actual casing layup, cured ply thickness, resin system, fibre/resin fraction, conductivity along both fabric directions and through thickness, heat capacity, and their temperature dependence. Also obtain the resin/bond thermal limits and degradation data. Use the supplied density provisionally only with its material identity recorded. Elasticity and thermal-expansion data cannot supply the missing thermal properties.

### Phenolic and aluminium

For regression checks, retain the v0 virgin/char property tables and reaction model: reference densities 1250/600 kg/m³, Arrhenius `A = 333 s⁻¹`, `Ea = 64081 J/mol`, order 1, and pyrolysis enthalpy 418 kJ/kg. These are inherited assumptions until checked against the Iris phenolic grade, reinforcement, cure and char yield. Identify the mass basis of reaction enthalpy and use it consistently in the material routine and energy audit.

The old aluminium constants are 2700 kg/m³, 167 W/(m·K), and 896 J/(kg·K). Use them only for reproducing the previous model. Production cases need the actual alloy and temperature-dependent properties. Any casing temperature limit must come from the alloy/temper condition or composite resin system; melting temperature or carbon-fibre strength alone is not a pressure-casing acceptance criterion.

## Heating history and exposure

The specification currently leaves heat flux pending. Obtain the following for **each motor**:

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

The prior constant gas temperature of 2230.85 °C, coefficient of 1000 W/(m²·K), pressure of 800 ± 200 psi, and exterior conditions are **regression inputs**, not new motor specifications. The reaction written in `motorspec.md` does not determine wall heat flux, equilibrium gas fractions, particle heating or char-consumption kinetics.

If grain shielding is unknown, a liner exposed from ignition can be a clearly labelled screening scenario. It is not an established exposure history or a guaranteed worst case for every failure mechanism. Model supplied axial variations with separate representative stations initially, then include axial conduction where needed.

## ANSYS model and implementation sequence

### 1 Prepare a reproducible four-case model

Create a new version under the Iris directory, with shared physics and four explicit configurations. Generalize the old aluminium-specific geometry/material fields and constant boundary conditions. Keep the earlier studies as references. Validate radii, layer thicknesses, volumes, material assignments and units analytically before meshing.

Continue with native MAPDL transient thermal analysis and the existing UserMatTh/controller approach. Use the known 2026 R1 toolchain initially, recording the exact solver and library versions; rebuild and recheck the user routine if the solver version changes. Prepare the native database and input deck, then run a no-solve preflight before any transient job.

### 2 Establish the radial reference and sector model

Begin with cylindrical radial conduction to check geometry, thermal resistance and transient storage. The production reference will use the previous **SOLID278 thin sector**, with explicitly meshed phenolic rows so consumption can move the hot surface. SOLID278 supports transient conduction and oriented orthotropic conductivity; the casing material axes require an explicit check. [ANSYS SOLID278 reference][solid278]

Start from a 0.1° sector and a representative 50 mm axial coupon only where loading and construction are locally uniform. Use adiabatic cut faces only when compatible with the material tensor and assumed symmetry. Benchmark any shortened coupon against the 50 mm reference and preserve acceptable element shapes. Scale integrated mass/power by sector angle; do not scale temperature, heat flux or recession. Actual motor length is needed before reporting whole-motor totals.

Represent CF with separate solid ply regions and local thermal axes when layup data are available. A homogenized casing is acceptable for screening only after matching through-thickness thermal resistance and areal heat capacity to the layered model. Use ACP, if helpful, to define and inspect the actual layup; the fin tutorial's static-structural workflow is not itself a burnthrough solver.

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

Run Sustainer Al, Sustainer CF, Booster Al and Booster CF with identical numerical settings within each pair. Save complete histories through ignition, burning, tailoff and sufficient cooling to capture the casing temperature peak. If burnthrough occurs first, retain the event checkpoint; further heating of exposed casing requires an appropriate casing/bond degradation model.

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
| Radial resolution | Compare 120/240/480 phenolic rows for the sustainer and 160/320/640 for the booster: matching pitches of 39.6875/19.84375/9.921875 micrometres. Refine casing, axial and angular meshes independently where they affect the answer. |
| Time resolution | Start from the inherited 0.0125 s coupling step; compare with 0.00625 s and refine further near rapid conversion, load changes and burnthrough. Keep material-law parameters fixed. |
| Result convergence | Target less than 5% change in burnthrough time between the two finest runs, with a reported event bracket. If no crossing occurs, target agreement in remaining thickness within the larger of 0.02 mm or 1% of initial thickness; target casing peak agreement within 5 K. Tighten if a design decision lies within these tolerances. |
| Mass and energy | Retain the starting v0 gates: mass residual at most 1e-6 of initial liner mass, step energy residual at most 5%, and hot-load mismatch at most 2%. Also audit cumulative energy including gas, reaction terms and material removal. Investigate systematic drift and use absolute tolerances near zero power. |
| Solver outputs | Recheck the actual version's face heat-rate exports and user-source accounting. Preserve the previous independent reconstruction of pyrolysis/gas sinks where native outputs omit them; do not assume identical channel behaviour for a changed model. |

Measure pilot runtime and storage before committing to the full matrix. The previous 152,000-element model was expensive; reducing redundant axial/angular resolution must be justified by benchmark agreement. Use separate case directories, sealed input hashes, accepted checkpoints and complete restart partitions. Preserve errors and stop on failed audits rather than treating partially exported states as results.

## Deliverables and next implementation milestone

The first implementation milestone is a parameterized four-case geometry/material package, an input register distinguishing supplied data from inherited assumptions, a reproduced v0 regression case, and successful native preflights. Geometry and regression work can proceed while the heat loads, actual CF thermal data and consumption calibration are collected. Predictive production results depend on those inputs.

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

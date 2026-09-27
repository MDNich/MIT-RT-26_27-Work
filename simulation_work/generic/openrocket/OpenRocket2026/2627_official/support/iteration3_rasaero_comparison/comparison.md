# Iteration 3: OpenRocket vs RASAero II

The source ORK was exported through the MIT OpenRocket app. The exported model was configured and both motors were simulated through the RASAero II interface in the Windows 11 VM. OpenRocket values below are the **saved results in the supplied ORK**, not a fresh OpenRocket rerun. The original ORK is unchanged.

| Statistic | OR: I500T | RAS: I500T | OR: J570W | RAS: J570W |
|---|---:|---:|---:|---:|
| Apogee (m) | 366.96 | 377.45 | 822.09 | 873.98 |
| Reported peak speed (m/s) | 82.788 | 83.186 | 130.599 | 132.253 |
| Peak ground speed (m/s) | 82.788 | 83.131 | 130.599 | 132.198 |
| Peak acceleration (m/s²) | 79.181 | 78.403 | 158.700 | 158.555 |
| Peak Mach | 0.2440 | 0.2446 | 0.3850 | 0.3894 |
| Time to apogee (s) | 9.031 | 9.180 | 12.932 | 13.410 |

RASAero's apogee is **+2.86%** for I500T and **+6.31%** for J570W relative to OpenRocket.

RASAero’s reported velocity includes the wind-relative component; OpenRocket’s saved total velocity is ground-relative. The ground-speed row derives RASAero speed from its horizontal and vertical velocity components. RASAero acceleration and Mach peaks are extracted from the valid flight CSV exports. Values are predictions, with the model differences below.

## Identified model and simulation differences

| Item | OpenRocket source | RASAero representation / consequence |
|---|---|---|
| Fin cross-section | `triangular`, 29.6079603° included leading-edge angle, 0.370-in thickness | **Hexagonal Blunt Base**, 0.700-in leading-edge bevel, zero leading-edge radius. This matches the MIT implementation’s triangular nose followed by constant thickness and a square trailing edge. RAS Single Wedge would be a different, full-chord triangular section. User confirmed the hexagonal choice. |
| Fin control tabs | Four custom roll-tabbed trapezoidal fins; tab span 1.50 in, chord 1.28 in, offset 1.24 in; tab angle 0° | Four fixed trapezoidal fins with the same outer planform. No separate tab geometry, hinge gaps, tab aerodynamic derivatives, or active control. The source simulations have neutral tabs. |
| Fin fillets | 1.00-in fillet radius and fillet material specified | No explicit matching fillet geometry. Aggregate launch mass and CG are carried over. |
| Camera shells | Two opposite pods, each with a 2-in forward ogive and 2-in reversed ogive; 0.75-in diameter; centers 1.95 in from the axis; mounted 4.5 in into the MPT | Pods replaced by a streamlined, no-base-drag protuberance on the MPT with **0.369 in²** combined exposed frontal area. This approximates their drag and omits the explicit shapes and individual positions. |
| Camera drag overrides | Four nose instances each carry Cd override 0.023; aggregate contribution 0.092 to the rocket-reference Cd | That fixed Cd contribution is not transferred. RAS calculates protuberance drag from the frontal-area model, so camera drag is not aerodynamically identical. |
| Internal structure and mass distribution | Separate bulkheads, couplers, rings, avionics, CO₂ canisters, recovery hardware, and component mass overrides | These are not independent RAS components. Their contributions are represented by the exported aggregate loaded mass and CG. Detailed component inertia and mass distributions are not preserved as an editable assembly. |
| I500T motor and mass/CG | AeroTech I500T; raw export mass 14.3789 lb, CG 40.0738 in | The export lacked an I500T motor reference; selected **I500T-14A (AT)**. GUI values **14.38 lb / 40.07 in** differ by +0.000499 kg / −0.0000965 m from the raw export. |
| J570W motor and mass/CG | AeroTech J570W; raw export 15.0538 lb / 40.4660 in | **J570W (AT)** and those values preserved. Both apps use their own motor database entries; integrating the exported thrust histories agrees within 0.03% for both motors, a consistency check rather than proof of identical interpolation. |
| Recovery event | 24-in chute, Cd 0.8; motor ejection 14 s after burnout. Actual deployments at 15.336 s (I500T) and 16.053 s (J570W) | Same chute size and Cd, but **deployment at apogee** because the RAS recovery options do not express the original motor-delay event. Flight duration, deployment speed, descent, landing speed, and drift are not matched comparisons. The unused 656.168-ft altitude field remains present but does not control the apogee event. |
| Surface finish | Normal | Exported as **Rough Camouflage Paint**. This is the exporter’s category mapping; the two roughness/skin-friction models are not guaranteed equivalent. |
| Wind | Mean 2 m/s, standard deviation 0.2 m/s (10% turbulence), direction 90° | Steady 4.4739 mph (approximately 2 m/s); the source turbulent wind history and 3D direction are not reproduced. |
| Location and flight dynamics | Latitude 28.61°, longitude −80.6°, spherical geodetic model; time step setting 0.05 s with adaptive integration | No matching latitude/longitude/geodetic inputs in this model. RAS has different dynamics, gravity/atmosphere implementation, integration, and aerodynamic correlations. The source records tumbling shortly before apogee (8.718 / 12.577 s); equivalent attitude evolution is not established. |
| Unit conversion and precision | Metric source dimensions and launch settings | Inch/foot/pound inputs are rounded. For example, the 30-in MPT exports as 29.9999 in, its location is saved as 25.8 in versus raw-export 25.7999 in, and the rail is 3.2808 ft versus 1 m. These errors are negligible for this comparison. |
| Cosmetic/file differences | Original component names, materials, and colors | RAS uses simpler component records; edited body sections display black rather than the export’s blue. A native save also normalizes XML fields such as unused CD/CP placeholders. These are not additional physical corrections. |

## Settings matched

Main body diameter 4.02 in; overall length approximately 62.8 in; 13.05-in tangent-ogive nose; body sections 2.75, 10, 30, and 7 in. Four fins have root chord 6 in, tip chord 2 in, span 3.26 in, sweep 4 in, thickness 0.37 in, and leading edge 6.5 in forward of the aft tube base. Launch is vertical from sea level with a 1-m rail, 15°C temperature, and approximately 101325 Pa pressure. No explicit launch lugs/rail-guide geometry or nozzle diameter was added.

## Interpretation

At their respective peak-speed samples, OpenRocket reports Cd ≈0.557 / 0.572 for I500T / J570W; RASAero reports ≈0.433 / 0.435. The lower RAS drag is consistent with its higher speed and apogee, but this comparison does not isolate the cause: camera drag treatment, friction correlations, wind, attitude, and other solver differences all remain. It would be inaccurate to attribute the whole difference to fin shape.

## Files and reproducibility

- [Configured RASAero model](iteration3-configured.CDX1)
- [I500T flight export](I500T-flight.csv)
- [J570W flight export](J570W-flight.csv)
- [RASAero flight-summary screenshot](rasaero-flight-summary.png)
- [RASAero launch-settings screenshot](rasaero-launch-settings.png)
- [Original MIT OpenRocket export](mit-openrocket-raw-export.CDX1)
- [Saved OpenRocket baseline and conditions](openrocket-baseline.json)
- [Machine-readable comparison](comparison-results.json)

The Windows account uses comma decimal formatting, which initially produced ambiguous CSV and CDX1 numeric values. RASAero was relaunched with English number formatting for this process, without changing Windows regional settings or the installed RASAero binary. Both simulations were rerun and the final model was saved natively; final CSV files have valid 24-column records and the CDX1 contains dot-decimal numbers. The corrected model reopened and reproduced both results. When reopening later, use the task launcher at `C:\Users\Public\Documents\CodexRASAero\RASAero-EnglishNumbers.exe` to avoid the same locale issue.

The MIT OpenRocket exporter wrote the geometry/simulation export but raised an unsupported motor-ejection recovery error. Its generated file was preserved before the dialog removed it; recovery was then configured in the RASAero GUI as documented above.

Source: `/Users/mdn/Developer/MIT_Rkt_Team/2026-7/MIT-RT-26_27-Work/simulation_work/generic/openrocket/OpenRocket2026/2627_official/20267.demonstrator.iteration3.ork`

Source SHA-256: `84d7050c7ee09c0cfb9ca1b7fbc00d615f9bb4f9398624104d69511defb20032`

References: [RASAero II manual](https://www.rasaero.com/dloads/RASAero%20II%20Users%20Manual.pdf), especially p. 15 (airfoils), pp. 24–25 (protuberances), and pp. 81–82 (recovery); MIT OpenRocket `FinSet.java`, `leadingEdgeDistanceFromAngle` and `getFinVolumeFactor`, which define its triangular leading-edge geometry.

# Native RASAero II afterbody campaign

RASAero II 1.0.2.0 ran thirteen static designs and a separate two-stage Iris flight on 9 November 2026 in the Windows 11 Parallels VM.

## Reading the exports

Each [native CDX1](models/) has a matching [original Aero Plots CSV](rasaero/). The models were opened and saved through the native editor. The CSVs came from **Aero Plots → File → Export → To CSV File** with the plot limit set to Mach 3. The exporter includes its full table through Mach 25. Each file contains 7,499 rows and 15 numeric columns, with its original precision, header and row order.

The [geometry and run manifest](manifest.csv) gives one row per external part. It records nose-referenced stations, lengths, outside radii, serialized diameter fields, fin root stations, and SHA-256 digests of the model and output. All dimensions are inches. Each case has every Mach value from 0.01 to 3.00 in steps of 0.01 at 0°, 2°, and 4° incidence, giving 900 checked samples per case and 11,700 across the campaign.

## Controlled geometry

Each family holds the nose and overall length fixed. The boattail or flare replaces the final section of the straight cylinder. The intermediate step terminates in an aft cylinder.

| Case | Nose and body | External afterbody, inches |
| --- | --- | --- |
| A-straight | 12-in tangent ogive, 4-in body OD | Cylinder from station 12 to 60 |
| A-boattail | Same | Cylinder to 56, conical boattail from 56 to 60, 4.00 → 3.00 OD |
| A-flare | Same | Cylinder to 56, conical flare from 56 to 60, 4.00 → 4.80 OD |
| A-step | Same | Cylinder to 48, widening taper from 48 to 48.5, 4.00 → 4.20 OD, then 4.20 OD to 60 |
| B-straight | 9-in conical nose, 3-in body OD | Cylinder from station 9 to 45 |
| B-boattail | Same | Cylinder to 42, conical boattail from 42 to 45, 3.00 → 2.40 OD |
| B-flare | Same | Cylinder to 42, conical flare from 42 to 45, 3.00 → 3.60 OD |
| B-finned-straight | B-straight plus three fins | Same 45-in base station |
| B-finned-boattail | B-boattail plus the same three fins | Same taper and 45-in base station |
| C-finned-straight | 18.50-in tangent ogive, 5.00-in body OD, four fins | Cylinder from station 18.50 to 67.50 |
| C-finned-boattail | Same | Cylinder to 61.50, conical boattail from 61.50 to 67.50, 5.00 → 4.50 OD |
| Iris-constant-finless | 32-in von Kármán ogive, 4.02-in body OD | One 104.50-in cylinder from station 32 to 136.50 |
| Iris-constant-finned | Same, plus four Iris fins | Same 136.50-in base station |

Families A, B and C use smooth surfaces with zero roughness, fully turbulent flow, and the default CP method. Their native static configurations have no motors, boosters, or protuberances. The B fins are square-section trapezoids with 4.5-in root chord, 2-in tip chord, 2.25-in span, 2.5-in sweep and 0.125-in thickness. The fin editor measures the root leading edge from the aft end of the parent tube. Its readings were 9.0 in on the straight control and 6.0 in on the boattail model. Both place the root at stations 36.0–40.5, entirely forward of the taper.

The C geometry was specified as a reserved comparison before its native results were available. Its four square-section trapezoids have 6-in root chord, 2-in tip chord, 3.5-in span, 4.5-in sweep and 0.15-in thickness. Setbacks of 13.5 in on the straight body and 7.5 in on the shorter cylindrical parent of the boattail place both fin roots at stations 54.0–60.0.

The Iris pair uses the archived half-inch sustainer [finned](../iris-components/models/finned.CDX1) and [finless](../iris-components/models/finless.CDX1) geometries. The first 50-in tube was extended to 104.5 in and both steps and their downstream tubes were removed. Both variants preserve the original 0.3693967 in² camera protuberance, rough camouflage finish, default CP method and source turbulence setting. The four original Hexagonal Blunt Base fins attach to the extended tube on the finned case. The native editor confirmed 8 in from the parent tube base to the root leading edge. The original 8-in root, 3-in tip, 3.5-in span, 5-in sweep, 0.25-in thickness and 0.7469705-in leading-edge bevel are preserved. Root stations remain 128.5–136.5.

## Native diameter fields

A contracting terminal section has a separate case-sensitive `BoatTail` record. Its `Diameter` and `RearDiameter` hold the forward and aft ODs. The parent `BodyTube` also stores `BoattailLength` and `BoattailRearDiameter`. Those describe the same taper, counted once in the manifest. The native boattail editor confirmed the forward diameter, rear diameter, and length for each contracting case.

Expanding terminal sections and the intermediate widening step use native `Transition` records. The previous tube supplies the forward OD shown in the transition editor. The native-saved campaign models write the aft OD in both `Transition/Diameter` and `Transition/RearDiameter`. The editor dimensions were checked against the saved records for each flare and the intermediate step.

To distinguish the two transition fields, one was changed at a time from 4.20 to 4.30 in diagnostic copies of A-step. The adjacent tubes stayed at 4.00 and 4.20. The table gives the native editor readouts and the number of differing values against the canonical A-step across its 900-point grid. The thirteen campaign models use the consistent native serialization.

| Field changed | Editor front OD (in) | Editor rear OD (in) | Changed CP rows | Changed CN rows | Changed power-off CD rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| RearDiameter | 4 | 4.2 | 0 | 0 | 0 |
| Diameter | 4 | 4.3 | 900 | 600 | 900 |

Here, the native editor and Aero Plots both used Transition/Diameter for the rear diameter. Changing RearDiameter alone gave a byte-identical full export. The preceding body tube stayed at 4.00 inches in both editor readbacks. The [diagnostic inputs](models/field-checks/) and [original diagnostic CSVs](rasaero/field-checks/) are separate from the physical comparisons in the manifest. Each diagnostic filename names the one altered field.

| Diagnostic | Input SHA-256 | Output SHA-256 |
| --- | --- | --- |
| RearDiameter | 323dc6174473770cb06f4aa785d2b04eb3c7f672e753233966689399df52b093 | 53a9a85b0c2c4342c7bc95917ea954dec78721d40b984ac0e52dc128c0f66390 |
| Diameter | 691ccc5c18f97c54ef5f7b5c79a8e1a7ee6724c1448f4ba1dd52f6c68a7a8214 | 39543553337dc5aaf5e1873d1baa8884915adca10e52281c8fe5bb5c0fcc93c4 |

## Native coefficient spot check

At Mach 2.80 and 2° incidence, the following values use the angle-specific CP in inches aft of the nose and the dimensionless total CN. The CSVs preserve the full native precision.

| Case | CP (in) | CN | Power-off CD |
| --- | ---: | ---: | ---: |
| A-straight | 13.41168 | 0.1283311 | 0.2773823 |
| A-boattail | 9.08505 | 0.1175276 | 0.2274698 |
| A-flare | 22.06119 | 0.1096952 | 0.2362549 |
| A-step | 20.56168 | 0.1486730 | 0.2735448 |
| B-straight | 10.22845 | 0.1166367 | 0.2633102 |
| B-boattail | 7.47184 | 0.1077509 | 0.2183766 |
| B-flare | 17.32456 | 0.1015835 | 0.2264988 |
| B-finned-straight | 25.08605 | 0.2440162 | 0.5015344 |
| B-finned-boattail | 24.38429 | 0.2351303 | 0.4566009 |
| C-finned-straight | 36.81171 | 0.2307038 | 0.4369914 |
| C-finned-boattail | 36.02232 | 0.2251774 | 0.4094113 |
| Iris-constant-finless | 37.69781 | 0.1253200 | 0.3122997 |
| Iris-constant-finned | 96.66011 | 0.3264736 | 0.4725825 |

## Two-stage Iris flight replay

The [as-run CDX1](iris-flight/Iris-half.CDX1) and selected [motor file](iris-flight/Iris-motors.eng) are byte-identical to the corresponding [archived half-inch inputs](../native-iris-half/README.md). The native Flight Simulation recalculated the O6836 booster and N3366 sustainer flight. The [new flight CSV](iris-flight/Iris-half-flight.csv) matches the archived CSV byte for byte, including all 16,664 time samples and 24 columns. Apogee was 83,949.06 ft at 77.14597 s, with peak speed 2,860.204 ft/s and peak Mach 2.81805.

The Aero Plots range was returned to its initial Mach 25 setting after each export. A fresh RASAero process identified the same active motor database before and after the replay. The temporary campaign-folder share was removed after verification.

| Flight file | SHA-256 |
| --- | --- |
| Iris-half.CDX1 | 8235c3fa86959f1f5b1930ca1d1e21a74c71b96251bb0af18ce0d40a42efba9d |
| Iris-motors.eng | e84f2fb2cb72c725893c87b278f42ca4ef7a5347109d80c67d04727af3299c5f |
| Iris-half-flight.csv | ce9e09ae12f3ab909dd49bd2303abf1df4cadf338ff84462dca308f55d8da901 |

# Iris component probes at small incidence

Native RASAero II 1.0.2.0 ran all three sustainer shapes in the Windows 11 Parallels VM on 8 November 2026. These single-stage virtual flights sample the external aerodynamics near Mach 2.80. Each recorded CP, lift, and drag value below comes from an actual time step.

## Native static input limit

The documented **Tools → Run Test** dialog accepts a user-selected angle. In this installed build its Alpha field is a FarPoint FpInteger control with a 32-bit integer value. Both ordinary typing and pasting 0.01 produced 1 in that field. Setting the visible edit text to 0.01 also left the native forebody export at 1.00° at Mach 2.80. Its total-CN/CP record read `2.80   1.00    0.046   20.935`. That run was excluded. The published guide describes the static output layout in Figure 108. [RASAero II user manual, pp. 86–90](https://www.rasaero.com/dloads/RASAero%20II%20Users%20Manual.pdf)

## Flight inputs and exports

Each [probe CDX1](models/) preserves the complete RocketDesign element of its [source component model](../models/), including all component dimensions and the original camera representation. Load [coefficient-probe.eng](models/coefficient-probe.eng) with **File → Select Motor File**, then open the desired CDX1. Its Flight Simulation configuration produces the [original 0.01 s CSV export](rasaero/) through **View Data → File → Export → To CSV**. The file stems identify the geometry and rail setting.

The virtual test motor replays every time and thrust entry from the [Iris N3366 curve](../../iris/Iris-motors.eng). Its synthetic RASP header uses the identifier N3367 (CoefficientProbe), 25.4 mm diameter, 50.8 mm length, 0.001 kg propellant, and 0.100 kg loaded motor mass. The chosen test weight of 24.25085 lb (11 kg) takes each shape through Mach 2.80 while keeping mass and CG nearly constant. These weights, CGs and launch conditions describe coefficient probes. The flight models have no booster, no recovery deployment, and zero nozzle exit area. All use sea-level launch altitude, 59 °F, 29.9214 inHg, and a 3.2808 ft guide.

| Run | Guide from vertical (deg) | Steady wind (mph) | Loaded CG aft of nose (in) | Native flight rows |
| --- | ---: | ---: | ---: | ---: |
| forebody | 0 | 0.25 | 12 | 18,829 |
| finless-inclined | 8 | 1 | 12 | 14,678 |
| finned | 0 | 0.25 | 75 | 11,167 |

## Time-step selection

[samples.csv](samples.csv) retains the 24 native fields for the selected rows. [neighbors.csv](neighbors.csv) adds the two preceding and two following samples in source order for each selection. Line numbers are one-based and count the CSV header as line 1. The half-inch Iris mission check comes from the [existing native two-stage flight](../../native-iris-half/Iris-half-flight.csv), using only the separated sustainer.

Both branches are ascending in altitude. Powered ascent has positive thrust and coasting ascent has zero thrust. Within each branch, eligible samples have positive vertical velocity, |Mach − 2.80| ≤ 0.01 and 0 < |α| < 0.05°. When available, samples with |α| ≥ 0.001° take priority. Among eligible samples in the chosen range, the smallest absolute Mach difference wins, with the earlier sample breaking a tie. If no sample qualifies within that Mach window, the search extends to ±0.02, recorded in the mach_window_used column. The powered finless sample uses this wider window. All rows are native time steps.

| Run | Branch | Time (s) | Mach | Native α (deg) | Native CP (in aft of tip) | Native CL | Native lift (lbf) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| forebody | powered ascent | 3.249997 | 2.801421 | -0.0002338757 | 17.04047 | -0.0000006920858 | -0.0005996749 |
| forebody | coasting ascent | 14.42023 | 2.800353 | -0.000005296246 | 17.04011 | 0.00000001034109 | 0.000001774974 |
| finless-inclined | powered ascent | 3.519997 | 2.814433 | -0.03009264 | 38.64062 | -0.002610522 | -2.4371 |
| finless-inclined | coasting ascent | 8.5301 | 2.791146 | 0.04107549 | 38.71891 | 0.004021655 | 1.834301 |
| finned | powered ascent | 4.029997 | 2.799095 | 0.00001503728 | 98.89307 | 0.000002141645 | 0.001882866 |
| finned | coasting ascent | 6.040043 | 2.800495 | 0.000002786994 | 98.88163 | 0.0000006033601 | 0.0004041025 |
| half-inch-mission-check | powered ascent | 20.55028 | 2.799734 | 0.0003992029 | 98.88718 | 0.00005562031 | 0.02316311 |
| half-inch-mission-check | coasting ascent | 20.82029 | 2.800661 | 0.0004205759 | 98.87949 | 0.00005926136 | 0.02378908 |

RASAero exports wind-axis CL, CD, lift and drag for these flights. It does not export a body-axis CN column in Flight View Data. The tables preserve RASAero’s signed native values and row order. Near zero incidence, the ratio of force to the same row’s angle is sensitive to time-step alignment, particularly at a sign crossing. The neighboring rows allow that alignment to be examined separately. Altitude, thrust, airspeed, and attitude are available for every sample in the raw files.

RASAero displayed its Marginal Stability notice for forebody. The notice reported positive stability below the program’s recommended margin during part of the run. The native static-margin time histories are preserved in the full flight files.

The previous Windows motor file selection was restored after testing. A fresh native RASAero process identified `C:\Mac\Home\Documents\RASAero II\rasp.eng` as its selected engine file.

## SHA-256 digests

The paths below are relative to this directory.

```text
9d5b91875090f49247ef9a103b7d6389b3367d8fd40abe3b9dbf0f067251fa58  ../models/forebody.CDX1
930b8918f94b35d792d2763af3eb0bbfa076abec8c54ef01379f217d991d33dc  ../models/finless.CDX1
ea7166741acdc3c839b7870259065b6f6d5866e552a03aa8091b6a67a25b75ad  ../models/finned.CDX1
7dfda08187f0bd1de1e980e369e7bd386e25d3fee7944f6180fd0dc859b64fa5  models/coefficient-probe.eng
1be0e95d939c760a68b809cca9e2deab841ad1f341e1c8139a040f4d568f3ca1  models/finless-inclined-probe.CDX1
71ca286e2666524fc5bc89f4dc88a5a132e943f437f0df760c3f07dbcadf800f  models/finned-probe.CDX1
14fa6cb8cb9b527ed1f15353965b09c0960c3110867a5cda743036d29a79b480  models/forebody-probe.CDX1
4b730e0221651febf1dabba8b94805989437b01fdc324eac5aa747b5d3585ad2  neighbors.csv
5f27db612cb38edfb9020fed103d4d66cba84f8feb79693fe17e99526072eda5  rasaero/finless-inclined-flight.csv
530a7e38e64c37e920167fe60112051d369755b11b63a4262141df07362e99e9  rasaero/finned-flight.csv
94e2e024ff2a497dd8d9952900931ec6cac3a22736928c76e2e8d3761a54ce48  rasaero/forebody-flight.csv
3aa8bbb58108fb6fa7a37d69b3e8dd7aa37e7d5d2bef55bb83cb29928a250470  samples.csv
ce9e09ae12f3ab909dd49bd2303abf1df4cadf338ff84462dca308f55d8da901  ../../native-iris-half/Iris-half-flight.csv
```

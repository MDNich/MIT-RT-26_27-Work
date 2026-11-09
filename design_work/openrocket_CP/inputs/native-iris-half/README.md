# Iris 0.50-inch sustainer transition

RASAero II 1.0.2.0 ran this two-stage case in the Windows 11 VM on 8 November 2026. The native model carries the new flight summary. The CSV is the original **Flight → View Data → File → Export → To CSV** output. It contains 16,664 time samples and 24 columns, including stage, Mach, CG and CP in inches aft of the nose tip, and static margin in calibers.

The geometry and mass reference is [preferred.ork](../iris/preferred.ork), SHA-256 `46bf2471c2addece61b0f8d03c4d07099d9ef77f7fe73f0bac2a1f274231f97b`. The first sustainer transition begins at station 82.00 in and is 0.50 in long. All downstream stations move aft 0.25 in relative to the [historical 0.25-inch model](../iris/Iris_Nov8.CDX1). The second transition begins at 127.50 in and is 1.00 in long. The booster begins at 136.50 in and overall length is 239.25 in.

The loaded properties were independently checked in OpenRocket with the digest-matched custom curves, then entered in RASAero in pounds and inches.

| Configuration | Loaded mass (kg) | CG aft of nose (m) | CG aft of nose (in) |
| --- | ---: | ---: | ---: |
| Full stack | 73.229153296 | 4.142629948 | 163.0956672 |
| Sustainer | 26.076044156 | 2.423703117 | 95.4213826 |

The O6836 booster and N3366 sustainer use the included motor file. The native flight used 5 s from booster burnout to separation and 5 s from separation to sustainer ignition. The first sustainer sample occurs at 10.530 s and the first positive sustainer thrust at 15.520 s.

The controlled comparison retains the historical CDX1 representation. The booster cylinder uses 6.17 in diameter across the 6.00 in motor-case section. The two sustainer transition records retain the exporter's paired diameter fields of 4.17/4.17 and 4.20/4.20 in, so their local taper aerodynamics are approximate. Camera shells use equivalent streamlined protuberance areas. Both nozzle exit diameters are zero and recovery hardware contributes mass only. The launch is vertical from sea level, on a 1 m guide in a steady 2 m/s wind.

| Native result | Value |
| --- | ---: |
| Apogee | 83,949.06 ft (25,587.67 m) |
| Time to apogee | 77.14597 s |
| Peak velocity | 2,860.204 ft/s (871.790 m/s) |
| Peak Mach | 2.81805 |

The apogee is 1,393.35 ft (424.69 m) above the historical native result. The CSV maxima for altitude, time to apogee and speed agree with the saved CDX1 to export precision.

SHA-256 values for the deliverables:

```text
8235c3fa86959f1f5b1930ca1d1e21a74c71b96251bb0af18ce0d40a42efba9d  Iris-half.CDX1
ce9e09ae12f3ab909dd49bd2303abf1df4cadf338ff84462dca308f55d8da901  Iris-half-flight.csv
e84f2fb2cb72c725893c87b278f42ca4ef7a5347109d80c67d04727af3299c5f  Iris-motors.eng
```

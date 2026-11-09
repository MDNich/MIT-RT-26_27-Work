# Iris camera protuberance sensitivity

The zero-area cases match their originals exactly in exported CP, CN and potential CN at all 906 matched points.

## Native runs

On 8 November 2026, RASAero II 1.0.2.0 in the Windows 11 Parallels VM opened the [finless](models/finless.CDX1) and [finned](models/finned.CDX1) designs separately. Each input differs from its [matching sustainer model](../models/) only in the first body tube’s `Protuberance/StreamlinedNoBaseDrag` value, changed from 0.3693967 in² to 0. Restoring the original numeric text reproduces the original CDX1 byte for byte. Both runs use the inherited default CP calculation, surface finish, turbulence setting and 4.20-in maximum diameter.

Each [original native CSV](rasaero/) came from **Aero Plots → File → Export → To CSV File** with the plot limit set to Mach 3. Native exports include the higher-Mach tail. The input copies opened in Windows were byte-checked against the supplied models.

## Matched comparison

The [pointwise table](comparison.csv) joins each new export to its [original export](../rasaero/) by exact Mach and angle of attack. Differences are zero-area minus original, calculated directly from the exported decimal values. Each of the six groups has all 151 Mach values, 1.50 through 3.00 inclusive in 0.01 steps. CP is the angle-specific native column in inches aft of the nose. CN and CN Potential are the original dimensionless body-axis coefficients.

| Case | Angle | Points | Max absolute ΔCP (in) | Max absolute ΔCN | Max absolute ΔCN Potential |
| --- | ---: | ---: | ---: | ---: | ---: |
| finless | 0° | 151 | 0 | 0 | 0 |
| finless | 2° | 151 | 0 | 0 | 0 |
| finless | 4° | 151 | 0 | 0 | 0 |
| finned | 0° | 151 | 0 | 0 | 0 |
| finned | 2° | 151 | 0 | 0 | 0 |
| finned | 4° | 151 | 0 | 0 | 0 |

Power-off drag was checked on the same samples to establish whether the solver responds to the area change.

| Case | Changed CD Power-Off samples | Min signed ΔCD Power-Off | Max signed ΔCD Power-Off |
| --- | ---: | ---: | ---: |
| finless | 453 / 453 | -0.0079294441 | -0.0047809610 |
| finned | 453 / 453 | -0.0079294441 | -0.0047809610 |

## File identities

SHA-256 digests for the paired model inputs and native outputs, with paths relative to this directory.

```text
930b8918f94b35d792d2763af3eb0bbfa076abec8c54ef01379f217d991d33dc  ../models/finless.CDX1
3466f9341cc734b9020b6fe550d77c9a2aaec7d1465e0b3695d75b839aa1c5a9  ../rasaero/finless.csv
3c4a3e0ebcfa07a50c990b1af0d709f8c645ad051cfad6cd73b485c95d40cb01  models/finless.CDX1
e1f1a53b801a1529caf3a8004367b744b8aac36ef11049438e2d4faf8f1ed9d5  rasaero/finless.csv
ea7166741acdc3c839b7870259065b6f6d5866e552a03aa8091b6a67a25b75ad  ../models/finned.CDX1
a07aa4176c95b8ec155769275dd58e019ad5f4fcb1c9cc6d9f9f35542b9cbdfa  ../rasaero/finned.csv
c72189a4fb6496ca6b9cff432f7fc1c4062aa43fdc06bdbc50ba811d37c6ba12  models/finned.CDX1
7e964dbd7dcbc213bd493309bfc81f306e41174abb85d5b8203985747df067c2  rasaero/finned.csv
```

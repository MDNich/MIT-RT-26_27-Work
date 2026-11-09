# Iris sustainer static aerodynamics

On 8 November 2026, native RASAero II 1.0.2.0 in the Windows 11 Parallels VM opened each [CDX1 model](models/) separately. **Aero Plots → File → Export → To CSV File** produced the [original coefficient exports](rasaero/). Match filenames by basename.

| Case | Geometry retained from the native 0.50-inch Iris model | Length (in) | Max diameter (in) |
| --- | --- | ---: | ---: |
| forebody | 32-in von Kármán nose and first 50-in bare tube | 82.0 | 4.02 |
| finless | All six sustainer parts, including the camera protuberance on the first tube | 136.5 | 4.20 |
| finned | The finless geometry plus the four original sustainer fins | 136.5 | 4.20 |

The source is [Iris-half.CDX1](../native-iris-half/Iris-half.CDX1), SHA-256 `8235c3fa86959f1f5b1930ca1d1e21a74c71b96251bb0af18ce0d40a42efba9d`. All three inputs use the source's rough camouflage paint finish, default CP method (`ModifiedBarrowman=False`), `Turbulence=False`, zero sustainer nozzle diameter and launch-site settings. Booster geometry and motor flight configurations were removed for these static calculations.

The complete sustainers use the original native 0.50-in transition at station 82.0 in and 1.00-in transition at 127.5 in. Their inherited diameter/rear-diameter pairs are 4.17/4.17 in and 4.20/4.20 in. Their camera representation is a streamlined, no-base-drag area of 0.3693967 in². The fins are the native Hexagonal Blunt Base section with 8-in root, 3-in tip, 3.5-in exposed span, 5-in sweep, 0.25-in thickness and 0.7469705-in leading-edge bevel. The reference frontal areas from the maximum diameters are 12.69235 in² for the forebody and 13.85442 in² for the complete sustainers.

The plot limit was Mach 3. Each native CSV retains 7,499 rows and extends to Mach 25. Verification found every Mach point from 0.01 to 3.00 in steps of 0.01 at each of 0°, 2° and 4°. Each row's original `CP` is the location in inches aft of the nose tip and `CN` is the body-axis normal-force coefficient. The separate `CP (0 to 4 deg)` column is also present. Each model's component records were compared with the retained source elements and all exported coefficient columns were checked for finite numeric values.

SHA-256 of the stored inputs and native outputs:

```text
9d5b91875090f49247ef9a103b7d6389b3367d8fd40abe3b9dbf0f067251fa58  models/forebody.CDX1
0ff1216c0cfc20a9c0ac93fbe937a5b940d0ecdf2c381da722d8cc3564077bc4  rasaero/forebody.csv
930b8918f94b35d792d2763af3eb0bbfa076abec8c54ef01379f217d991d33dc  models/finless.CDX1
3466f9341cc734b9020b6fe550d77c9a2aaec7d1465e0b3695d75b839aa1c5a9  rasaero/finless.csv
ea7166741acdc3c839b7870259065b6f6d5866e552a03aa8091b6a67a25b75ad  models/finned.CDX1
a07aa4176c95b8ec155769275dd58e019ad5f4fcb1c9cc6d9f9f35542b9cbdfa  rasaero/finned.csv
```

# RASAero II static CP holdouts

On 8 November 2026, native RASAero II 1.0.2.0 in the Windows 11 Parallels VM opened each CDX1 design. Each coefficient CSV was exported separately through **Aero Plots → File → Export → To CSV File** with the plot limit set to Mach 3.

The models share a 12-inch tangent-ogive nose, one 48-inch cylindrical tube, a 4-inch diameter and four square-section trapezoidal fins of 0.125-inch thickness. Each root trailing edge is 0.5 inches forward of the tube base. Settings are smooth (zero roughness), fully turbulent flow and the default CP model (`ModifiedBarrowman=False`). Nozzle exit diameter is zero. The three fin geometries were chosen before generating coefficients. Each differs from all 92 September atlas models, including after normalizing tip chord, span and sweep distance by root chord.

All dimensions below are inches. Sweep is the axial distance between root and tip leading edges. Root leading-edge position is measured aft of the nose tip.

| Model | Root chord | Tip chord | Exposed span | Sweep | Root leading edge |
| --- | ---: | ---: | ---: | ---: | ---: |
| short-span | 6.75 | 2.75 | 1.125 | 0.625 | 52.75 |
| wide-unswept | 5.5 | 3.375 | 6.25 | 0 | 54 |
| highly-swept | 10.25 | 1.75 | 3 | 8.5 | 49.25 |

Each basename pairs its [CDX1 model](models/) with its [original RASAero export](rasaero/). RASAero wrote its full native sweep despite the plot limit. The [through-Mach-3 CSVs](through-Mach-3/) retain the original header and rows for Mach 0.01 through 3.00. Verification found 300 distinct Mach values at each of 0°, 2° and 4° per design, in 0.01 increments. Filter by `Alpha` before interpolating. The native `CP` column is the CP at the row’s angle in inches aft of the nose tip. The separate `CP (0 to 4 deg)` column is available for the interval-based comparison.

SHA-256 of the original native CSV files:

```text
6b7a279e7aef03f20e58341b2922b768d94805b541c23aeb3477bcb9967497f7  short-span.csv
56a6b993a284abae06d88b5adfd8fc8a0c41c87515e70be055b7965c94a81980  wide-unswept.csv
4c46572d20826a3a8ed9129e87e53c6dba73d7f9e9d698a49e02ba362bf094d5  highly-swept.csv
```

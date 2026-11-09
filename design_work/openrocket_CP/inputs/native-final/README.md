# Final independent RASAero II static CP cases

All three CDX1 geometries were frozen at 2026-11-08T19:47:32-05:00 before starting the native exports. The input file digests are in [models.sha256](models.sha256). The tip chord, exposed span and sweep distance normalized by root chord distinguish each planform from all 92 September atlas cases and the three preceding November holdouts.

Dimensions are in inches. Sweep distance is the axial offset of the tip leading edge relative to the root leading edge. The angle is measured from a transverse line.

| Basename | Fin count | Body diameter | Root chord | Tip chord | Span | Sweep distance | LE sweep |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| three-fin-moderate | 3 | 3.25 | 5.25 | 2.375 | 3.125 | 2.25 | 35.8° |
| four-fin-tapered | 4 | 4 | 7.5 | 0.75 | 4.125 | 3.75 | 42.3° |
| four-fin-near-rectangular | 4 | 4 | 4.75 | 4.5 | 3.875 | 0.125 | 1.8° |

Each design has a tangent-ogive nose three diameters long and a cylindrical tube twelve diameters long. Each fin has a square cross section, 0.125 in thickness and its root trailing edge 0.5 in forward of the tube base. The default RASAero CP model is selected (ModifiedBarrowman=False), with smooth surface, fully turbulent flow and zero nozzle exit diameter.

Native RASAero II 1.0.2.0 ran each frozen model in a separate Windows 11 session of the application in Parallels. Each [original CSV](rasaero/) was written by **Aero Plots → File → Export → To CSV File**. The plot limit was Mach 3. Each native export contains 7,499 rows and extends to Mach 25. Match each CSV to its [CDX1 file](models/) by identical basename.

The [Mach 0.01–3.00 subsets](through-Mach-3/) contain the original header and original data lines. Each design has 300 finite samples at each of 0°, 2° and 4°, with a Mach increment of 0.01. The native `CP` column gives the angle-specific position in inches aft of the nose tip. RASAero also exports the separate `CP (0 to 4 deg)` column. The three angle-specific CP histories differ across the designs.

Verification after export reproduced all three frozen model hashes and the exact subset rows. The [native CSV checksums](rasaero.sha256) record the original output bytes.

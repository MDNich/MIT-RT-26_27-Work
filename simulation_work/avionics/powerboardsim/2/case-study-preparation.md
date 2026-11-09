# Power board with battery case

Prepared 8 November 2026. The enclosure STEP and its SolidWorks source arrived later that evening. The comparison assembly is the populated October power board. Its three cells transfer load to the rest of the model through six cell-to-nickel connections, two per cell. Whether the new case supports the cells continuously or engages after clearance closes is the first question for the revised model.

## Starting files

The [original board CAD and ECAD inputs](../1/src/), [modal report](../1/output/pdf/power_board_modal_comparison.pdf), [random-vibration report](../1/output/pdf/power_board_random_vibration.pdf) and [lateral-pull report](../1/output/pdf/power_board_battery_side_pull.pdf) are in revision 1. The [later nickel damage draft](../1/output/latex/battery_side_pull/nickel_tearing_estimate.tex) records both accepted partial histories and rejected attempts.

For the native Workbench project, the fuller local archive is at `/Users/mdn/Developer/MIT_Rkt_Team/2026-7/MIT-RT-26_27-Work/simulation_work/avionics/powerboardsim/1`. It contains `powerboardsim_v1.wbpj`, the 214 MB Mechanical database under `powerboardsim_v1_files/dp0/global/MECH/SYS.mechdb`, modal/static decks and native result files. The refined frictional-pull preflight, solve and postprocessing decks there match their archived SHA-256 entries. Stage a working copy of the required inputs for the case revision. Recheck linked geometry, ECAD, materials, selections and contact pairs after import.

## Baseline comparisons

| Quantity | October result and scope |
|---|---|
| Assembly and mounting | 208 meshed bodies, about 0.25182 kg. Eight fixed stand-off end faces. Six screws tightened to 750 N each, then locked. An assumed washer contact offset closed about 0.746 mm of CAD clearance. |
| Modal | First prestressed mode 485.964 Hz. Two modes with substantial battery motion occurred at 645.435 and 781.350 Hz. A disconnected nine-body battery group affected the original default model. Use the connected, preloaded assembly for the main comparison. |
| Random vibration | Separate X/Y/Z base cases, 20–2000 Hz, 14.136 g RMS from log-log integration and 2% assumed modal damping. The solution used 38 prestressed modes through 3986 Hz. Largest PCB relative directional displacement was 0.052674 mm RMS under Z excitation. Largest PCB equivalent-stress RMS was 90.325 MPa under X excitation. |
| Local edge-cell pull and tearing | The two 0.15 mm nickel strips were modeled with a rigid cell, an idealized weld footprint and locally supported clamps. The continuous nominal damage calculation first exceeded its reporting threshold at 3.250–3.275 mm and 42.870–43.372 N under the assumed material law. The partial curve ended while force was rising. Rupture load remains open. The follow-up excluded earlier bilinear pull values pending a history audit. |

## Sequence after STEP delivery

1. Check units and coordinate alignment using mounting-hole centres, board faces and cell axes. Identify the case material, attachment hardware, pads or adhesive. Measure initial gaps or interference at each cell and the board. Map how the case transfers force to the mounts.
2. Rebuild the assembly contact pairs and named selections. Check connectivity, supported rigid-body motion, mass and centre of gravity, washer seating and fastener reactions. Establish the case contact state in static equilibrium before modal extraction.
3. Repeat the modal comparison and the three original base spectra about the new equilibrium. Expand the mode set until response and participating mass are adequate for the excitation band. Compare corresponding mode shapes, relative cell-to-case travel, and board stress and displacement. If predicted travel can close a gap or open a support, evaluate that change in a nonlinear contact transient. Regenerate comparable seeded motion and stress histories from the new modes.
4. Repeat the displacement-controlled edge-cell pull in both lateral directions. Carry the measured clearances and case support into the local model, track force carried by case versus tabs, and check clamp reactions, force/moment balance and mesh sensitivity at the bends and welds. Report damage onset and any demonstrated separation with their respective evidence.

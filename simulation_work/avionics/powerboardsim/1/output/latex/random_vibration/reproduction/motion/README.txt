Random-vibration motion reproduction supplement, 6 October 2026.
Read sections 19 onward of power_board_random_vibration.tex before reuse.

The original project root is the powerboardsim/1 directory. T denotes its
outputs/random_motion_20261005_2143 directory. Scripts retain these project
relationships and the documented Windows C:\Temp paths. They are evidence
and reproduction sources, not a one-click installer. Create a NEW runtime,
adapt paths and verified IDs, and preserve original result files.

The three complete native solves use 750 N per fastener, the 38-mode
prestressed basis, 2% damping, separate seeded X/Y/Z base acceleration,
65536 Hz integration, and a 9 s duration. The video window contains 480
states at 16384 Hz from 1.00006103515625 to 1.029296875 s.

Included CSVs retain the MCF's rounded time column for provenance.
For exact video times use 1 + (frame_index+1)/16384, not rounded MCF times.
The supplied generate_input.py recreates all input samples from the seeds.
Large binary Workbench, modal restart, and result files remain in the
preserved project/native archives identified by the report and manifests.
They are not duplicated in this compact source bundle.

Rendering uses native Mechanical fields and geometry. Every evaluated result
must have the expected time before export. Keep the camera and legend fixed.
Reject repeated/stale result states caused by a lost license. Encode only
480 valid 3840x2160 images at 60 fps; decode the complete output for checking.
Displacement is relative to the base, visually multiplied by 50. Playback
is slowed by 16384/60. The result is one seeded realization, not an RMS movie.

Dynamic stress is reconstructed from six modal stress components in global
coordinates before evaluating von Mises. Static clamp stress is excluded.
The Figure 18 motion view uses elemental-nodal, unaveraged stress values.
The source manifest and per-video audits record the completed outputs.

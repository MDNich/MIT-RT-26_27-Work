# Gyro-integral attitude correction — 27 September 2026

This record supersedes the telemetry-pose interpretation in the earlier rocket-view records. The renderer had incorrectly treated independent body-axis gyro integrals as absolute Euler angles. The packet and CSV ordering were correct; the conversion from those values to an orientation was not.

The original Zephyrus firmware (`Avionics2025/RT_Firmware_Libs/gyro.cpp`, lines 57–59) accumulates `roll += -gyroX*dt`, `pitch += gyroY*dt`, and `yaw += gyroZ*dt`. `RT_Arduino/Zephyrus/FC/FC.ino` transmits these degree totals at payload offsets 64/68/72 and zeroes them on entering Preflight and Flight. They do not encode an absolute attitude quaternion. Recorded gyro saturation also prevents assuming a reliable recovered attitude from these data.

The corrected telemetry view preserves the raw totals under integral labels (∫R, ∫P, ∫Y) and shows a muted neutral model with a prominent **ORIENTATION UNAVAILABLE** caption. The neutral model is not a claim that the rocket is upright. No orientation is forced from climb, phase or simulation data. The historical tilt formula remains available as **Legacy tilt proxy**, with its original CSV field and values preserved.

An explicitly supplied, validated body-to-ENU quaternion with a +Z nose can orient the telemetry model through the internal decoded adapter contract documented in the station guide. No firmware command, wire protocol or sensor-fusion implementation was added. OpenRocket's existing quaternion orientation remains unchanged.

## Validation

- [578 tests passed](tests.txt), covering wire/CSV compatibility, all station layouts, recording/replay and existing controls.
- [21 renderer checks passed](renderer-tests.txt) after simplifying the final caption.
- [Real GS1/GS2/GS3 climb regressions](climb-regression.json) verify that raw values remain unchanged and cannot become false absolute attitude. At launch +10 s, the old conversion produced about 111.6° of tilt; the corrected result explicitly reports attitude unavailable.
- Model tests exercise known quaternion rotations, chirality, stale inputs and rejection of invalid frame/axis metadata, malformed or nonfinite values and nonunit quaternions.
- [20 packaged checks passed](packaged-verification.json), including offline bundled OpenRocket and the station/video profiles.
- Ruff F and Git whitespace checks passed; the native arm64 Mac app passed strict deep signature verification. [Build checksum and source hashes](results.json).

[Climb +2 s](climb-2s.png) · [Climb +10 s](climb-10s.png) · [Corrected readout](pose-climb-10s.png) · [Unchanged simulation pose](simulation-pose.png)

Screenshots use recorded Zephyrus data and a synthetic simulation fixture, with local hardware disconnected. No physical equipment or Windows/universal Mac build was tested. The native app and installer were rebuilt, intermediate build directories removed, and changes pushed normally without a release.

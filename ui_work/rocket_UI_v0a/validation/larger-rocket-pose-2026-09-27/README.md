# Larger rocket graphic — 27 September 2026

The rocket graphic now occupies the full pane width, with roll/pitch/yaw, motor/parachute indicators and source/status text below it. Framing reserves space only for visible effects, stays fixed as the rocket rotates, and fits the complete body, plume and canopy across the tested orientations. The camera remains upright and controlled only by the azimuth slider.

Launch gives the rocket two rows and places the angular-rate and integrated-rotation plots side by side below. Away gives the rocket three rows in the center column, with the altitude plot below. All existing instrument categories and controls remain visible.

- [45 focused checks passed](tests.txt): renderer, source integration, station layouts, shortcuts and complete table visibility.
- [12 final layout checks passed](away-layout-tests.txt) after enlarging the Away pane.
- Ruff F and Git whitespace checks passed.
- [20 packaged checks passed](packaged-verification.json), covering the startup wizard, station/video profiles, recording/replay, virtual pointing and bundled OpenRocket with a minimal system PATH.
- The rebuilt native macOS arm64 app passed strict deep signature verification. [Build checksum and source hashes](results.json).

[Launch telemetry](launch-demo-uplink.png) · [Launch live startup](launch-live.png) · [Launch motor](launch-motor.png) · [Launch parachute](launch-parachute.png) · [Away motor](away3-motor.png) · [Away parachute](away3-parachute.png)

These are 1920 × 1020 Qt renderings. DEMO uses recorded Zephyrus data; reference effects use a synthetic trajectory fixture. Hardware was disconnected and Away Wi-Fi status was stubbed. No physical equipment or Windows/universal Mac build was exercised in this revision. The existing unknown-status and telemetry/reference separation behavior is retained.

The current app and installer are `dist/RocketGNCMonitor-v0a.app` and `dist/RocketGNCMonitor-v0a-Darwin-arm64.dmg`. Build intermediates were removed after verification; changes were pushed normally without a release.

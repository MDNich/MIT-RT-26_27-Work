# Launch telemetry board and compact rocket pose — 27 September 2026

This record supersedes the local-board inventory in the earlier same-day Launch station record. Launch has **one local telemetry board**, using the existing Zephyrus connection, polling and decoding path. There is no separate uplink board and no local antenna pointer. The four LTU-XR links and Away pointer selection remain independent of this local input.

The Launch telemetry workspace exposes a firmware-placeholder uplink switch. In LIVE and REPLAY its hardware state is explicitly **UNKNOWN** and the switch is unavailable. In DEMO it starts **OFF**, can simulate **ON/OFF**, and gates simulated rocket commands. Changing modes resets the simulated switch to OFF. No uplink-enable bytes have been invented or sent. Iris has one shared Sustainer/Booster telemetry-board target selector, also a DEMO-only placeholder until its firmware command is defined.

The video role is unchanged: Launch has one local Digital USB receiver, while its wall shows all configured system channels and Away feeds. Analog remains an Away input. The video operator has no visible serial or uplink controls.

The circular attitude horizon is replaced throughout the telemetry workspaces and legacy instrument view by a compact animated 3D rocket. Its camera has only an azimuth slider, with world vertical kept upright and no dragging, panning or wheel zoom. All three reported angles affect the illustrative pose. Flame and parachute effects require explicit telemetry flags or an explicitly selected OpenRocket reference. Existing Zephyrus data does not supply those confirmation flags, so the Telemetry view shows UNKNOWN. Reference playback shows its own time and playback state, and missing event histories remain unknown independently for motor and parachute.

## Validation

- [528 suite tests passed](tests.txt), including one-board reception, existing connect/poll shortcuts, live uplink lockout, simulated switch behavior/reset, single Iris target, video inventories and rocket-pose replacement.
- [80 focused pose tests passed](pose-tests.txt) after the final reference time/provenance and partial-event-history refinements. These verify all three angles, fixed vertical, ignored drag/wheel input, flame/chute gating, stale/unknown status, source separation and hidden-window timer shutdown across Launch, Away and legacy layouts.
- [12 follow-up integration/layout checks passed](layout-tests.txt) after compacting the route panel. These cover the fuller Iris/URRG DEMO layout with a selected Away route and verify every route label fits at 1920 × 1020.
- Ruff F and Git whitespace checks passed.
- [20 packaged checks](packaged-verification.json) passed with a minimal system PATH, including startup, wizard, all station/video profiles, recording/replay, GS1/GS2/GS3, virtual pointing and bundled OpenRocket.
- Additional packaged-report checks confirmed exactly one Launch serial role (`telemetry`), a visible uplink placeholder only in its telemetry role, unknown hardware switch state, simulated switch initially OFF, and only Digital as the Launch video input. They also confirmed the new rocket renderer and azimuth slider are visible in telemetry layouts, hidden in video layouts, and default to telemetry with unknown effects.
- The final native macOS arm64 app passed `codesign --verify --deep --strict`. [Installer checksum and source hashes](results.json) identify the build.

[LIVE layout](launch-live.png) · [DEMO with simulated uplink ON](launch-demo-uplink.png)

[Launch reference ignition](launch-motor.png) · [Launch reference parachute](launch-parachute.png) · [Away reference parachute](away3-parachute.png) · [Compact rocket and flame](pose-motor.png) · [Compact rocket and parachute](pose-parachute.png)

The screenshots are Qt renderings with local hardware disconnected; DEMO uses recorded Zephyrus data, and the reference animation uses a synthetic test trajectory with explicit events. Away screenshots use an empty Wi-Fi status fixture. Serial integration tests use fake boards. Physical boards, receivers and interstation transport were not exercised. Windows and universal Mac builds were not refreshed. Notarization remains deferred.

The current app and installer are retained in `dist/RocketGNCMonitor-v0a.app` and `dist/RocketGNCMonitor-v0a-Darwin-arm64.dmg`. Build intermediates and duplicate PyInstaller staging were removed after verification. Changes were pushed normally without a GitHub release.

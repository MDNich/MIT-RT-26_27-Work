# Launch station, Away Wi-Fi and rocket-state validation — 27 September 2026

The current app calls the former Base station **Launch station**. An explicit Launch profile creates no serial workers or local antenna controls. Its communication panel shows Ethernet / PoE, four LTU-XR routes and a choice of Away 1–4 antenna pointers. Selecting a route records operator intent only. Live uplink and remote pointer commands remain unavailable until the interstation transport is specified. Away telemetry retains its downlink board, physical/virtual pointer controls and keyboard shortcuts.

Away profiles provide an editable Wi-Fi selection, saved network names, read-only operating-system status and a button to open native Wi-Fi settings. Joining/authentication takes place in system settings. Network selection does not imply an operational telemetry/video link. No passwords are stored.

The Systems window now has a large upper-right rocket-state badge driven by telemetry: green GROUND_TESTING, blue PREFLIGHT, red FLIGHT, orange POST_APOGEE / MAIN / END, black unknown or missing state. Raw recorded state names take precedence over the legacy importer's fallback state code. LIVE / DEMO / REPLAY and stale data are explicitly identified.

## Evidence

- [445 passing tests](tests.txt), including state decoding, unknown/stale state handling, blocked Launch serial/transmission paths, preserved Away controls, Wi-Fi parsing and 1920 × 1020 table layout.
- Ruff undefined-name/import checks and Git whitespace checks passed.
- [20 packaged checks](packaged-verification.json) passed on macOS arm64 with a minimal system PATH. They cover startup, wizard, station/video profiles, saved flight, GS1/GS2/GS3 playback, virtual pointer, 3D events and bundled OpenRocket simulations, including the Zephyrus model fixture.
- Additional packaged report checks confirmed no local Launch serial roles or pointer controls, all four route choices, Away Wi-Fi visibility and the black NO TELEMETRY badge at startup.
- The final app passed `codesign --verify --deep --strict`.
- [Build identity and installer checksum](results.json).

## Visual review

- [Systems window with FLIGHT state](systems-flight-state.png).
- [Launch station with Away 3 route selected](launch-remote-pointer.png).
- [State colors, unknown and stale examples](rocket-state-colors.png).

Screenshots are Qt renderings at the target layout size. The full-window examples use a synthetic decoded Zephyrus packet in REPLAY mode; they are not evidence of a real flight or a connected link. No physical serial boards, cameras, radios, LTU-XR bridges or Wi-Fi joins were exercised. Packaged startup and simulation checks opened no physical serial hardware. Windows and universal Mac builds were not refreshed. The Mac app is locally signed; notarization remains deferred.

The refreshed application and installer remain in `dist/RocketGNCMonitor-v0a.app` and `dist/RocketGNCMonitor-v0a-Darwin-arm64.dmg`. Temporary `build` output and duplicate PyInstaller staging were removed after verification. Source changes were pushed normally; no release was created.

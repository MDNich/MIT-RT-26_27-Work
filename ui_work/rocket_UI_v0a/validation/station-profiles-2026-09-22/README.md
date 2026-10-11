# Station profiles validation — 22 September 2026

This record covers the station-profile, video-wall and serial-board changes in v0a. Earlier release validation records describe their respective builds and do not establish validation of these changes.

## Results

| Validation | Result | Evidence |
| --- | --- | --- |
| Final source suite, Qt offscreen | **273 passed in 77.20 seconds** | [Source test log](source-tests.log) |
| Repository lint (`make lint`, Ruff `--select F`) | **Passed**; this covers the repository-prescribed rules, not all optional Ruff rules | [Lint log](source-lint.log) |
| Windows native affected-module checks | **164 passed, 1 POSIX-only skip** across the initial suite and targeted Settings/camera reruns | [Windows results](windows/validation-summary.json) |
| macOS ARM64 packaged application | **20 checks passed before the final camera-parser correction**; final media-only change, startup, signing, DMG and ZIP integrity separately verified | [ARM64 full-suite evidence](arm64/), [final module comparison](intel/camera-final-arm64-module-delta.json), [final integrity checks](arm64/integrity.json) |
| macOS Intel packaged application | **20 checks passed before the final camera-parser correction**; final media-only change, startup and six camera regression tests passed | [Intel evidence](intel/) |
| Windows packaged application | **20 checks passed on the final ZIP** | [Windows evidence](windows/) |

The [first final-source attempt](source-concurrent-build-attempt.log) had 272 passes and one flight-export timeout while a build was also running. The [isolated flight-export retry](source-flight-recheck.log) passed in 5.21 seconds; the final full suite subsequently passed. Concurrent work is context, not an established cause of the timeout. A subsequent [source attempt](source-video-restart-attempt.log) had 272 passes and one video-restart timeout. The recording restart could spend up to five seconds stopping FFmpeg before delivering frames, but the test allowed six seconds total. Its restart budget is now 20 seconds with worker/error diagnostics; all frame, recording and flight round-trip assertions remain. The isolated corrected test passed in 3.58 seconds. The final full suite passed all 273 tests, including both previously timed-out cases, with no package builds running concurrently. These test-only timing and diagnostic changes do not change the packaged application.

The final Windows camera correction uses unique DirectShow device identifiers when USB receivers have identical display names. Its macOS enumeration path is unchanged. Comparisons against each previously verified Mac payload found only `rocket_gnc_monitor.media` changed among 662 Python modules, with unchanged bootstrap members. The final Intel startup and six camera regression checks passed; both final universal launcher architectures have separate startup evidence. See the [camera-update record](intel/CAMERA_PARSER_UPDATE.md), [targeted package checks](intel/camera-final-package-checks.json), [camera regression log](intel/camera-tests.log), and [universal launcher checks](universal/launcher-checks.json).

The full Mac package suites were not rerun after that final correction; the 20-check reports cover the earlier payloads and the linked comparisons and targeted checks cover the update. The Windows full suite covers the final ZIP. The Mac full-suite reports and subsequent module comparisons must be read together; they do not represent rerunning every Mac check after the parser correction.

Final distributable hashes and sizes are recorded in [release-artifacts.json](release-artifacts.json).

## Configuration and routing covered

- Startup setup has three pages: station, role and vehicle. It offers Base and Away 1–4, Telemetry or Video, and Balius or Iris; remembers accepted defaults; and cancels before creating a controller.
- Video has its own window. Telemetry layouts retain the Base two-window workspace and the reduced Away workspace. Digital and analog camera selections remain exclusive.
- Windows receiver discovery preserves distinct device identities for cameras with identical display names, allowing two such receivers to be selected separately while maintaining physical-camera exclusivity.
- Balius has Digital and Analog channels. Iris has Sustainer Digital, Sustainer Analog and Booster Analog. Iris Away 1–3 receive the first two channels; Away 4 receives Sustainer Digital and Booster Analog. Base Video has one local digital input. Both vehicle configurations have eight remote thumbnails, containing only the two channels assigned to each Away station. The Iris Booster Analog primary defaults to Away 4.
- Base Telemetry has separate downlink and uplink boards plus the antenna-pointer board. Away Telemetry has a downlink board plus the antenna-pointer board. Serial-role inventories and connection exclusivity are checked; uplink input must not become downlink telemetry.
- Iris receiver selection remains a labelled placeholder because no hardware target-switch command is defined. Base has independent downlink and uplink selectors; Away has only downlink. Only DEMO enables simulated switches. Simulation records its board and target, does not send a hardware command or change the recorded Zephyrus dataset, and clears its simulated state when leaving DEMO.

Packaged verification also exercises LIVE startup, the setup wizard, flight save/load, the virtual pointer, 3D flight events, GS1/GS2/GS3 playback, assigned Iris camera channels, the video-wall inventories, and OpenRocket simulation. It checks that LIVE Iris placeholder actions are disabled and have no confirmed target.

## Visual and native-input evidence

The [screenshots](screenshots/) capture the startup pages and representative Base/Away, Balius/Iris layouts. Station-window capture targets are **1920 × 1020**; this is the validated display target, not a claim about every screen size.

The [initial native shortcut attempt](native-shortcut-attempt.log) exposed a Cocoa Settings-menu problem: Qt interpreted the Mission “Configure” action as Preferences, taking Command-comma away from Settings. Mission actions now explicitly use `NoRole`; the corrected [native Settings test passed](native-settings-fixed.log). The earlier combined shortcut/serial test also missed an expected event. The shortcut test used a fixed 40 ms delay; it now waits for the actual QAction signal while preserving keyboard events and wire assertions. The [final isolated native shortcut test passed](native-shortcuts-final.log). Both initial native failures are resolved by the menu fix and event-based test synchronization, with the original attempts preserved for context.

## Remaining integration limits

The multi-station video/APRS transport awaits the station-link protocol; the existing one-peer, read-only telemetry/status link does not carry video. Thumbnails and source selection do not imply an operational network connection. Physical serial boards, receiver target switching, antenna actuation and USB camera hardware have not been validated by this record. The Iris target-switch placeholders must remain inactive in LIVE and REPLAY until the firmware interface is implemented and tested.

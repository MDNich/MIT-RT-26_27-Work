# v0a acceptance records — 22 September 2026

The newest [station-profile and video-role validation](station-profiles-2026-09-22/README.md) covers the startup wizard, five station identities, Balius/Iris video, and refreshed packages. The workspace record below is historical.

The [cross-platform release validation](cross-platform-2026-09-22/README.md) records the subsequent universal Mac and Windows builds, including the refreshed Apple Silicon installer. The original package checksum and platform limits below are historical.

This record applies to the separate v0a application. The inherited v0 validation report is historical and is not the acceptance record for this workspace revision.

## Workspace review

Base station exposes 23 instrument panels across two coordinated windows; Away station exposes six panels in one window. The design target is two 1920 × 1080 displays, with about 1920 × 1020 usable window space. Automated layout checks use that size. Native screenshots were captured on the available Mac display at 1800 × 1020 logical pixels (3600 × 2040 backing pixels).

All normal rows in the fixed telemetry, GPS, servo, battery, power, BMS, recovery and actuator tables remain visible. Arbitrary-length event history, raw decoded JSON and wind profiles can scroll within their own panels. Configuration editors, file pickers and command confirmations remain dialogs.

Screenshots use recorded Zephyrus telemetry, generated video test patterns and an illustrative OpenRocket simulation. They are UI evidence, not a physical launch or equipment acceptance test.

- [Base station — Flight and antenna](screenshots/base-flight.png)
- [Base station — Systems and video](screenshots/base-systems.png)
- [Away station](screenshots/away.png)
- [Flight display in daylight theme](screenshots/base-day.png)
- [Systems display in daylight theme](screenshots/systems-day.png)
- [Virtual-pointer controls](screenshots/virtual-native.png)

## Reproducible checks

Run `make test` and `make lint` from the v0a root. Build the native Mac application with the supplied Makefile, then run `make verify-package`; the verifier includes both station layouts and exercises the packaged runtime with a minimal system PATH. Pass `--model tests/fixtures/zephy_testlaunch.ork` to `scripts/verify_package.py` to include the supplied rocket fixture.

The final counts, package checksum, source hashes and validation limits are recorded in [results.json](results.json). The adjacent packaged-verification and package-integrity reports retain the measured values, including simulated flight events and video frame counts. Tests cover layout switching without losing mission/connection state, shared keyboard shortcuts, Escape preserving the embedded 3D panel, all visible fixed table rows, APRS parsing, local station communication and video-only recording/replay.

## Validation limits

- Current deployment target: macOS Apple Silicon. Windows Makefiles remain available, but this revision was not built or exercised on Windows.
- Two-window placement and screen-change handling are implemented; a physical two-monitor field setup still requires an equipment check. Native visual review used one available Mac screen, and automated geometry checks inspected each full-size window separately.
- Serial PCBs, physical USB receivers, radio audio, LTU equipment and AP hardware were not connected during these checks. Simulated video frames do not establish receiver-driver compatibility.
- Dire Wolf runs externally. The monitor supports receive-only KISS TCP uncompressed APRS positions; it does not configure the audio modem.
- The LAN shares read-only status snapshots with one peer. It does not relay video, forward commands or provide audio/video calls.
- LTU management metrics and analog receiver tuning require the actual equipment interfaces. No values or command protocols are fabricated.
- A short native probe with both windows, two generated video feeds and animated scenes measured about 22 frames per second for the 3D viewer on this host. Performance depends on display scaling and workload; this is not a 60 fps guarantee.
- The package is locally signed for integrity; distribution notarization is a separate release step.

See the [station guide](../docs/V0A_STATION_MODES.md) and [board mapping notes](../references/GROUND_STATION_BOARD_NOTES.md) for exact operating scope.

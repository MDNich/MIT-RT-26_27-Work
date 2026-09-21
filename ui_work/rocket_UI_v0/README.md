# Rocket GNC Monitor v0

A native Python 3.12 / PySide6 desktop app for the two Zephyrus boards, Digital and Analog USB video, antenna pointing, GNC monitoring, recording/replay, and OpenRocket trajectory comparison.

Open the packaged **RocketGNCMonitor.app** on Mac, or **RocketGNCMonitor.exe** inside the complete extracted Windows package. Production machines need no separately installed Python, Qt, Java, FFmpeg, or build tools. Keep the package intact. Hardware-specific USB drivers may still be needed. The Mac app opens in **LIVE**, on the connection control panel, with physical transports closed and each board’s controls enabled when that board connects. Choose DEMO explicitly for rehearsal; `make demo` also starts a rehearsal.

## Included

- Offline Zephyrus test-flight demo from GS1/GS2/GS3, with recorded receive timing, pause/seek/speed controls and launch cue; GS2 is the default.
- Lucida Grande Regular/Bold bundled and loaded privately across the application, including plots and antenna annotations.
- Launch-site entry in decimal latitude/longitude, MGRS, or Plus Codes, with offline conversion, a resolved-position readout and a URRG preset (`18TUN2061530290`).
- Eight workspaces: connection control panel, flight overview, antenna pointer, GNC/actuators, mission/wind, sessions/replay, diagnostics, and the full legacy rocket controls. USB board connection and rocket radio reception are shown independently.
- Independent telemetry/pointer serial workers; incremental Zephyrus decoding, checksum recovery, loss counters, clock rollover/reboot detection.
- Independent Digital and Analog USB camera/file streams, each with controls, frame status and segmented recording through bundled FFmpeg. Camera selectors exclude the other feed's assignment; serial selectors exclude the other connected board's port.
- Photo-informed articulated mount: four timber legs, turntable, elevation cradle, open grid reflector, Yagi and enclosed Avenger XR18 attached directly to the common elevation beam through the support pivots. Drag to orbit through any angle, scroll to zoom, and double-click to reset the camera.
- All legacy rocket controls: state advance, zero commands, roll/airbrake servo commands, PD activate, VTX power, power rails, pyro ARM/FIRE, and emergency recovery, with the original confirmations.
- Legacy serial workflow: separate connect/disconnect and polling, independent manual pointer operation, native UP/DOWN/LEFT/RIGHT/ZERO commands, ground-GPS freeze, and all ten keyboard shortcuts.
- One-click Start/Stop Logging writes both original 43-column good/bad-packet CSVs alongside the richer session recording.
- Configurable canard channels and four fin tabs. Legacy Zephyrus supplies four servo drives only; unavailable new demands/feedback remain blank.
- Manual/imported wind profiles and Open-Meteo profiles for a selected place/time, with cached provider response.
- Private Java/OpenRocket worker, bundled MITRT N8406 for the Zephyrus test model, additional `.eng`/`.rse` motors, reproducible nominal simulation, normalized ENU reference and same-time position comparison.
- Portable `.rktflight` Save/Open files (⌘S/⌘O), including mission, embedded model/motors, simulation and available recordings; saves can run during logging.
- Indexed SQLite replay, exact serial capture with CRCs, event timeline, legacy CSV import/export, video seek/offset, incomplete-session recovery, dark/daylight themes and acknowledged alerts.

Open **Settings…** with **⌘,** (Windows: **Ctrl+,**) to select an OpenRocket JAR, simulation time limit, recording folder and display theme. Preferences persist on this computer. **Use bundled** restores the included engine.

For hardware-free rehearsal, set **Mission → Configure → Antenna pointer**, connect **Virtual antenna pointer**, then use **Follow trajectory** after running OpenRocket or loading a reference. Manual controls and the original pointer shortcuts actuate the simulated mount.

## Develop and build

From this folder, with Python 3.12, GNU Make and JDK 17+:

```sh
make setup PYTHON=python3.12
make run
make test
make lint
# Build on the respective target OS:
make -f Makefile.macos all OPENROCKET_JAR="/path/to/swing-24.12.RC.01-all.jar"
make -f Makefile.windows all OPENROCKET_JAR="C:/path/to/swing-24.12.RC.01-all.jar"
```

Supply a complete team-fork JAR or download it with `make package-macos OPENROCKET_DOWNLOAD=latest` (pin with `OPENROCKET_DOWNLOAD=v6.2`). Local embedding also works directly with `make package-macos OPENROCKET_JAR="/path/to/OpenRocket-MIT-v6.2.jar"`. The current Mac package includes OpenRocket-MIT v6.2. The private Java runtime is downloaded and checksum-verified during `make runtime`. Both native Makefiles produce a complete runtime package. Windows PowerShell equivalents, signing and offline preparation: [BUILD.md](docs/BUILD.md).

[Legacy feature parity](docs/LEGACY_PARITY.md) · [Operator guide](docs/OPERATOR_GUIDE.md) · [Wire contract](docs/PROTOCOL.md) · [Implementation/validation status](docs/IMPLEMENTATION_STATUS.md) · [Third-party notices](docs/THIRD_PARTY_NOTICES.md)

The existing pointer firmware has no measured-pose report, acknowledgment, mechanical home or stop opcode. **Hold stops new targets; the last move can continue.** Live tracking uses the original ground-GPS freeze and barometric-height convention.

The simulator produces a **nominal reference**, not a qualified prediction of the new controlled vehicle. The team's physical rocket/motor model and new actuator feedback remain required for field qualification.

Original planning baseline: [development plan](DEVELOPMENT_PLAN.md), [antenna design](ANTENNA_POINTER_DESIGN.md), [reference audit](REFERENCE_AUDIT.md), [execution validation](VALIDATION_AND_EXECUTION.md). See current implementation status for what is implemented versus awaiting field/release acceptance.

## Built artifacts and validation

The September 21 Mac revision is available as `dist/RocketGNCMonitor.app` and `dist/RocketGNCMonitor-Darwin-arm64.dmg`, with a SHA-256 sidecar. Mac regression tests include captured outputs from the original UI, 118 rocket command cases, eight pointer cases, all CSV columns, all ten actual keyboard shortcuts, confirmation dialogs, and OS pseudo-serial integration. The full Mac regression run passed 101 tests, including virtual-pointer motion/tracking, profile persistence, physical-transport isolation, Settings persistence/shortcuts, local and release engine selection, download failure handling, both feeds, recording/replay and portable flights. Packaged Live startup, all three recorded demos/video, URRG/portable flight round trips, and OpenRocket checks are included in `make verify-package`.

The Windows ZIP remains the September 18 build (30 tests passed, one POSIX-only test skipped, in the Windows 11 ARM VM under x64 emulation). It has **not** been rebuilt for this revision; current work and validation target Mac only.

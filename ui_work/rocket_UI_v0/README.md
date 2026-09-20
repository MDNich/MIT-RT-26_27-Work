# Rocket GNC Monitor v0

A native Python 3.12 / PySide6 desktop app for the two Zephyrus boards, USB video, antenna pointing, GNC monitoring, recording/replay, and OpenRocket trajectory comparison.

Open the packaged **RocketGNCMonitor.app** on Mac, or **RocketGNCMonitor.exe** inside the complete extracted Windows package. Production machines need no separately installed Python, Qt, Java, FFmpeg, or build tools. Keep the package intact. Hardware-specific USB drivers may still be needed. The Mac app opens in **LIVE**, on the connection control panel, with physical transports closed and operating controls locked until the ground station connects. Choose DEMO explicitly for rehearsal; `make demo` also starts a rehearsal.

## Included

- Seven workspaces: connection control panel, flight overview, antenna pointer, GNC/actuators, mission/wind, sessions/replay, and diagnostics. USB board connection and rocket radio reception are shown independently.
- Independent telemetry/pointer serial workers; incremental Zephyrus decoding, checksum recovery, loss counters, clock rollover/reboot detection.
- USB camera discovery/capture, video-file input, and segmented recording through bundled FFmpeg.
- Photo-informed articulated mount: four timber legs, turntable, elevation cradle, open grid reflector, Yagi and enclosed Avenger XR18 attached directly to the common elevation beam through the support pivots. Drag to orbit through any angle, scroll to zoom, and double-click to reset the camera.
- Live control interlocks require the ground station; antenna commands additionally require the pointer board and calibration. Guarded absolute pointing, 5° target steps, explicit tracking/hold, and software reference reset.
- Configurable canard channels and four fin tabs. Legacy Zephyrus supplies four servo drives only; unavailable new demands/feedback remain blank.
- Manual/imported wind profiles and Open-Meteo profiles for a selected place/time, with cached provider response.
- Private Java/OpenRocket worker, custom `.eng`/`.rse` motors, reproducible nominal simulation, normalized ENU reference and same-time position comparison.
- Indexed SQLite replay, exact serial capture with CRCs, event timeline, legacy CSV import/export, video seek/offset, incomplete-session recovery, dark/daylight themes and acknowledged alerts.

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

The complete team-fork fat JAR is required at build time. The private Java runtime is downloaded and checksum-verified during `make runtime`. Both native Makefiles produce a complete runtime package. Windows PowerShell equivalents, signing and offline preparation: [BUILD.md](docs/BUILD.md).

[Operator guide](docs/OPERATOR_GUIDE.md) · [Wire contract](docs/PROTOCOL.md) · [Implementation/validation status](docs/IMPLEMENTATION_STATUS.md) · [Third-party notices](docs/THIRD_PARTY_NOTICES.md)

The existing pointer firmware has no measured-pose report, acknowledgment, mechanical home or stop opcode. **Hold stops new targets; the last move can continue.** Live tracking requires explicit origins, altitude interpretation, mount calibration and a verified continuous azimuth cable route.

The simulator produces a **nominal reference**, not a qualified prediction of the new controlled vehicle. The team's physical rocket/motor model and new actuator feedback remain required for field qualification.

Original planning baseline: [development plan](DEVELOPMENT_PLAN.md), [antenna design](ANTENNA_POINTER_DESIGN.md), [reference audit](REFERENCE_AUDIT.md), [execution validation](VALIDATION_AND_EXECUTION.md). See current implementation status for what is implemented versus awaiting field/release acceptance.

## Built artifacts and validation

The September 20 Mac revision is available as `dist/RocketGNCMonitor.app` and `dist/RocketGNCMonitor-Darwin-arm64.dmg`, with a SHA-256 sidecar. Mac tests: 35 passed, including real OS pseudo-serial connection transitions, corrupt/valid packet link indication, reconnect isolation, command locking, and camera orbit without changing antenna pose. Packaged Live startup, explicit demo/video, and OpenRocket checks are included in `make verify-package`.

The Windows ZIP remains the September 18 build (30 tests passed, one POSIX-only test skipped, in the Windows 11 ARM VM under x64 emulation). It has **not** been rebuilt for this revision; current work and validation target Mac only.

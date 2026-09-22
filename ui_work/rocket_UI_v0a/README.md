# Rocket GNC Monitor v0a

A native Python / PySide6 monitoring application with two station layouts. **Base station** opens two coordinated windows so flight, antenna, GNC, video, mission and support information remain visible. **Away station** presents the antenna pointer and main rocket telemetry in one reduced window. Station layout is independent of **LIVE**, **DEMO** and **REPLAY** data modes.

This is a separate revision of `rocket_UI_v0`; the original application remains available. Install **RocketGNCMonitor-v0a.app** alongside **RocketGNCMonitor.app** on Mac. v0a has a separate application identifier and preferences. The full package includes Python, Qt, Java, OpenRocket and FFmpeg; keep it intact when copying it to another computer. USB devices may require their manufacturer's drivers.

See the [v0a station guide](docs/V0A_STATION_MODES.md) for the screen arrangement and ground-station board connections, and the [validation record and screenshots](validation/README.md) for this revision.

## Station workspace

| Station | Windows | Information |
| --- | --- | --- |
| Base | Flight and Systems | Flight: main telemetry, plots/3D reference, antenna pointing and GNC. Systems: Digital/Analog USB video, rocket commands, power/recovery, mission/wind, network/APRS, sessions and diagnostics. |
| Away | One | Main rocket telemetry and antenna connection, visualization and control. |

The workspaces expose their monitoring sections together without the previous left-hand navigation tabs. Editors, file selectors and confirmations still open when an operator takes an action. The two base windows share one controller, mission, recording session and device connections.

The application starts in **LIVE**, with physical connections closed. Ground-station and pointer controls become available when their respective boards connect. USB video runs independently of the ground-station serial connection, including video-only recording once frames arrive. Both camera selectors prevent assigning one USB camera to both Digital and Analog video. Serial selectors exclude a port already connected by the other board. Choose **DEMO** explicitly for rehearsal; it uses the recorded Zephyrus GS1/GS2/GS3 datasets, with GS2 as the default.

The circuit-board map separates the telemetry USB board, pointer USB board, both USB video receivers and the APRS audio path through an external Dire Wolf KISS TCP decoder (default `127.0.0.1:8001`). The APRS panel receives uncompressed position reports, with an optional callsign/SSID filter. The LAN panel explicitly **Listens** or **Connects** to one peer on port `8765` for read-only status and telemetry snapshots. Neither connection starts automatically; the LAN does not transmit commands, audio or video. AP/LTU equipment supplies the local network, so these station connections work without internet access. LTU metrics and analog-receiver controls remain unavailable until their protocols are provided; audio/video calls are not implemented. The [board mapping notes](references/GROUND_STATION_BOARD_NOTES.md) distinguish implemented features from the diagram's suggestions.

## Retained capabilities

- Independent Zephyrus telemetry and antenna workers, original command workflow, confirmations and keyboard shortcuts, plus legacy good/bad packet CSV logging.
- Two USB video feeds labelled **Digital** and **Analog**, independent capture/recording, exclusive camera assignment, replay offsets and segmented FFmpeg recording.
- Smooth articulated antenna graphics with orbit/zoom, including the grid reflector, Yagi and enclosed Avenger XR18 on a common beam. Physical and virtual pointers share the same manual controls and original shortcuts.
- Launch and antenna positions using latitude/longitude or MGRS; launch Plus Codes and URRG preset (`18TUN2061530290`); launch-relative pointer heading, horizontal distance and altitude difference.
- OpenRocket trajectory simulation with bundled or selected team JAR, manual/imported/online wind, additional motors and reference comparison. Animated 3D playback shows attitude, recorded ignition/burnout events and parachute deployment. Older references without event/attitude columns remain usable; rerun them to add those details.
- Portable `.rktflight` Save/Open files (**⌘S / ⌘O**), mission/model/motor/reference/session storage, indexed replay, seek/speed controls and diagnostic events.
- **Settings…** (**⌘,**, or **Ctrl+,** on Windows) for the OpenRocket JAR, simulation time limit, recording folder and theme. Lucida Grande is bundled privately.

For hardware-free pointing rehearsal, specify the antenna location in the mission, connect **Virtual antenna pointer**, load or generate an OpenRocket reference and start **Follow trajectory**. Simulation is a nominal reference; the legacy Zephyrus protocol does not provide the proposed vehicle's complete canard/tab feedback. Those channels remain unavailable until real feedback is integrated.

## Develop and build

From this directory, with Python 3.12, GNU Make and JDK 17+:

```sh
make setup PYTHON=python3.12
make run                 # Base station: two windows
make away                # Away station: one window
make demo STATION=base   # Recorded Zephyrus rehearsal
make test
make lint
```

Build on the target operating system:

```sh
make -f Makefile.macos all OPENROCKET_JAR="/path/to/OpenRocket-MIT-v6.2.jar"
make -f Makefile.windows all OPENROCKET_JAR="C:/path/to/OpenRocket-MIT-v6.2.jar"
```

Or embed a release from the team GitHub repository:

```sh
make package-macos OPENROCKET_DOWNLOAD=latest
# Pin an explicit release for repeatable preparation:
make package-macos OPENROCKET_DOWNLOAD=v6.2
make verify-package
```

Only package preparation downloads the engine/runtime. Supplying `OPENROCKET_JAR` copies the local engine into the app; omitting engine options reuses the staged `vendor` files. `make runtime` prepares the private, checksum-verified Java runtime. Mac outputs are `dist/RocketGNCMonitor-v0a.app` and `dist/RocketGNCMonitor-v0a-Darwin-arm64.dmg` (architecture varies with the build host). Windows uses `RocketGNCMonitor-v0a.exe` in a complete ZIP package; build it natively on Windows. This revision's active packaging and UI validation target Mac.

The packaged verification exercises locked Live startup, the three recorded demos and both videos, portable flight files, URRG, virtual pointing and the private OpenRocket runtime/3D events with a minimal system PATH. Hardware acceptance still requires the actual boards, camera receivers and network equipment.

[Build details](docs/BUILD.md) · [Legacy feature parity](docs/LEGACY_PARITY.md) · [Inherited operator reference](docs/OPERATOR_GUIDE.md) · [Wire contract](docs/PROTOCOL.md) · [Third-party notices](docs/THIRD_PARTY_NOTICES.md)

The inherited v0 guides document individual controls and wire behavior; use the v0a station guide for their new screen arrangement. The pointer firmware still has no measured-pose report, acknowledgment, mechanical home or stop opcode. **Hold stops new targets; the last move can continue.**

# Rocket GNC Monitor v0a

A native Python / PySide6 monitoring application for one **Base station** and **four Away stations**. A startup wizard selects the station, **Telemetry** or **Video** role, and **Balius** or **Iris** vehicle. Telemetry uses two displays at Base and one reduced display at Away stations. Video has its own dedicated screen: two system channels for Balius, three for Iris, with receivers assigned by station. Station identity and role are independent of **LIVE**, **DEMO** and **REPLAY** data modes.

This is a separate revision of `rocket_UI_v0`; the original application remains available. Install **RocketGNCMonitor-v0a.app** alongside **RocketGNCMonitor.app** on Mac. v0a has a separate application identifier and preferences. The full package includes Python, Qt, Java, OpenRocket and FFmpeg; keep it intact when copying it to another computer. USB devices may require their manufacturer's drivers.

See the [v0a station guide](docs/V0A_STATION_MODES.md) for the screen arrangement and ground-station board connections, and the [validation record and screenshots](validation/README.md) for this revision.

## Station workspace

| Station / role | Windows | Information |
| --- | --- | --- |
| Base / Telemetry | Flight and Systems | Flight: main telemetry, plots/3D reference, antenna pointing and GNC. Systems: rocket commands, power/recovery, mission/wind, network/APRS, sessions and diagnostics. |
| Away 1–4 / Telemetry | One | Main rocket telemetry and antenna connection, visualization and control. |
| Away 1–4 / Video | One | Balius: Digital + Analog. Iris Away 1–3: Sustainer Digital + Sustainer Analog; Away 4: Sustainer Digital + Booster Analog. Independent USB selection, capture and recording/playback. |
| Base / Video | One | Two or three large channels above every Away station’s matching thumbnails. Local Digital USB input; remote sources await the future station video connection. |

The workspaces expose their monitoring sections together without the previous left-hand navigation tabs. Editors, file selectors and confirmations still open when an operator takes an action. The two base windows share one controller, mission, recording session and device connections. Video panels appear only in the Video role. The wizard appears at each launch with the previous selection remembered. Station identity and role remain fixed for that session; relaunch to choose another assignment. Double-click an Away thumbnail at Base to replace the matching large channel; other thumbnails remain available.

The application starts in **LIVE**, with physical connections closed. Ground-station and pointer controls become available when their respective boards connect. USB video runs independently of the ground-station serial connection, including video-only recording once frames arrive. All camera selectors prevent assigning one USB camera to multiple active channels, including Iris’s station-specific Digital/Analog pair. Serial selectors exclude a port already connected by any other board. Choose **DEMO** explicitly for rehearsal; it uses the recorded Zephyrus GS1/GS2/GS3 datasets, with GS2 as the default.

The supplied routing diagram describes **Balius**: Digital reception and telemetry at all five stations, Analog reception at Away stations only. The [Iris diagram](references/IRIS_STATION_ROUTING.png) assigns Sustainer Digital to every station, Sustainer Analog/telemetry/APRS to Away 1–3, and Booster Analog/telemetry/APRS to Away 4. Base combines the three video channels. Base has separate downlink and uplink telemetry boards; Away stations have downlink only. Iris target switching is explicitly a firmware placeholder, with independent DEMO simulations for the two Base boards and the Away downlink. The circuit-board map separates downlink/uplink USB boards, the pointer USB board, USB video receivers and the APRS audio path through an external Dire Wolf KISS TCP decoder (default `127.0.0.1:8001`). The APRS panel receives uncompressed position reports, with an optional callsign/SSID filter. The LAN panel explicitly **Listens** or **Connects** to one peer on port `8765` for read-only status and telemetry snapshots. Neither connection starts automatically; the LAN does not transmit commands, audio or video. AP/LTU equipment supplies the local network, so these station connections work without internet access. LTU metrics and analog-receiver controls remain unavailable until their protocols are provided; audio/video calls are not implemented. The [board mapping notes](references/GROUND_STATION_BOARD_NOTES.md) distinguish implemented features from the diagram's suggestions.

## Retained capabilities

- Independent downlink, Base-only uplink, and antenna workers; original command packets, confirmations and keyboard shortcuts, plus legacy good/bad packet CSV logging. Live Iris uplink commands remain locked while the target-switch contract is undefined; DEMO can exercise the placeholder switches and command UI.
- Two **Balius** channels (**Digital**, **Analog**) or three system-wide **Iris** channels (**Sustainer Digital**, **Sustainer Analog**, **Booster Analog**), with station-specific USB capture/recording, exclusive camera assignment, replay offsets and segmented FFmpeg recording. Each Away station exposes its two assigned receivers; Base Video exposes only its local Digital camera. Its remote thumbnails support matching-channel promotion and show honest connection/age status; the station video transport is pending.
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
make run                 # Startup wizard with remembered defaults
make away                # Wizard preselects Away 1 / Telemetry
make video VEHICLE=iris   # Wizard preselects Away 1 / Video / Iris
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

Only package preparation downloads the engine/runtime. Supplying `OPENROCKET_JAR` copies the local engine into the app; omitting engine options reuses the staged `vendor` files. `make runtime` prepares the private, checksum-verified Java runtime. Mac outputs are `dist/RocketGNCMonitor-v0a.app` and `dist/RocketGNCMonitor-v0a-Darwin-arm64.dmg` (architecture varies with the build host). Windows uses `RocketGNCMonitor-v0a.exe` in a complete ZIP package; build it natively on Windows. Mac packages require macOS 14 or newer. The universal package runs natively on Apple Silicon and Intel; the Windows package targets x64 (also tested through x64 emulation in the supplied Windows 11 ARM VM). See [universal Mac packaging](docs/MAC_UNIVERSAL.md) for its Makefile target and verification commands.

The packaged verification exercises the startup wizard, station/role profiles, two- and three-channel layouts, locked Live startup, the three recorded demos, portable flight files, URRG, virtual pointing and the private OpenRocket runtime/3D events with a minimal system PATH. Hardware acceptance still requires the actual boards, camera receivers and network equipment.

[Build details](docs/BUILD.md) · [Legacy feature parity](docs/LEGACY_PARITY.md) · [Inherited operator reference](docs/OPERATOR_GUIDE.md) · [Wire contract](docs/PROTOCOL.md) · [Third-party notices](docs/THIRD_PARTY_NOTICES.md)

The inherited v0 guides document individual controls and wire behavior; use the v0a station guide for their new screen arrangement. The pointer firmware still has no measured-pose report, acknowledgment, mechanical home or stop opcode. **Hold stops new targets; the last move can continue.**

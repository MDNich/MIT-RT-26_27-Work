# Rocket GNC Monitor v0a

A native Python / PySide6 monitoring application for one **Launch station** and **four Away stations**. A startup wizard selects Launch station or Away 1–4, **Telemetry** or **Video** role, **Balius** or **Iris** vehicle, and **URRG** or a custom launch site. Telemetry uses two displays at the Launch station and one reduced display at Away stations. Video has its own dedicated screen: two system channels for Balius, three for Iris, with receivers assigned by station. Station identity and role are independent of **LIVE**, **DEMO** and **REPLAY** data modes.

This is a separate revision of `rocket_UI_v0`; the original application remains available. Install **RocketGNCMonitor-v0a.app** alongside **RocketGNCMonitor.app** on Mac. v0a has a separate application identifier and preferences. The full package includes Python, Qt, Java, OpenRocket and FFmpeg; keep it intact when copying it to another computer. USB devices may require their manufacturer's drivers.

See the [v0a station guide](docs/V0A_STATION_MODES.md) for the screen arrangement and ground-station board connections, and the [validation record and screenshots](validation/README.md) for this revision.

## Station workspace

| Station / role | Windows | Information |
| --- | --- | --- |
| Launch station / Telemetry | Flight and Systems | Flight: main telemetry, plots/3D reference, remote antenna route and GNC. Systems: rocket command status, power/recovery, mission/wind, network/APRS, sessions and diagnostics. |
| Away 1–4 / Telemetry | One | Main rocket telemetry and antenna connection, visualization and control. |
| Away 1–4 / Video | One | Balius: Digital + Analog. Iris Away 1–3: Sustainer Digital + Sustainer Analog; Away 4: Sustainer Digital + Booster Analog. Independent USB selection, capture and recording/playback. |
| Launch station / Video | One | Two or three large channels above every Away station’s matching thumbnails. Local Digital USB input; remote sources await the future station video connection. |

The workspaces expose their monitoring sections together without the previous left-hand navigation tabs. Editors, file selectors and confirmations still open when an operator takes an action. The two launch windows share one controller, mission, recording session and device connections. Video panels appear only in the Video role. The wizard appears at each launch; **Remember these choices next time** is optional and off by default. Station identity and role remain fixed for that session; relaunch to choose another assignment. Double-click an Away thumbnail at the Launch station to replace the matching large channel; other thumbnails remain available.

New missions are named **Balius Launch** or **Iris Launch**. Choosing URRG fills the launch-pad location and, at Away stations, the local antenna location from the [URRG presets](docs/V0A_STATION_MODES.md#mission-and-antenna-positions). The Launch station has a site reference but no local pointer. Elevations remain manual. Opening a saved mission or flight uses its stored settings.

The application starts in **LIVE**, with physical connections closed. Ground-station and pointer controls become available when their respective boards connect. USB video runs independently of the ground-station serial connection, including video-only recording once frames arrive. All camera selectors prevent assigning one USB camera to multiple active channels, including Iris’s station-specific Digital/Analog pair. Serial selectors exclude a port already connected by any other board. Choose **DEMO** explicitly for rehearsal; it uses the recorded Zephyrus GS1/GS2/GS3 datasets, with GS2 as the default.

The Launch station connects by **Ethernet / PoE to four LTU-XR bridge links**, one for each Away station. Each Away station has its LTU-XR link and a local Wi-Fi network, plus its own downlink board and physical antenna pointer. Choose the Away station's Wi-Fi network in the UI, and at Launch choose which Away antenna pointer will serve as the communication route. Selecting either option records intent; the interstation telemetry/video/control protocols are pending. The Launch station has **no local serial board or pointer connection** and retains exclusive uplink authority. Live uplink and remote pointer actuation remain unavailable until their transport is defined.

The [Iris diagram](references/IRIS_STATION_ROUTING.png) assigns Sustainer Digital to every station, Sustainer Analog/telemetry/APRS to Away 1–3, and Booster Analog/telemetry/APRS to Away 4. The Launch station combines the three video channels. Iris target switching remains a labelled firmware placeholder with DEMO simulation. The existing APRS input uses an external Dire Wolf KISS TCP decoder (default `127.0.0.1:8001`). The existing LAN panel explicitly **Listens** or **Connects** to one peer on port `8765` for read-only snapshots; it is separate from the planned four-station transport and carries no commands, audio or video. LTU management readings, analog-receiver controls and calling remain pending their protocols. Earlier [board mapping notes](references/GROUND_STATION_BOARD_NOTES.md) describe the supplied reference diagrams; use the current station guide for the revised Launch architecture.

## Retained capabilities

- Independent Away downlink and antenna workers; original command packets, confirmations and keyboard shortcuts, plus legacy good/bad packet CSV logging. Launch-only uplink authority remains represented, with live commands locked while the station transport is undefined; DEMO can exercise the placeholder switches and command UI.
- Two **Balius** channels (**Digital**, **Analog**) or three system-wide **Iris** channels (**Sustainer Digital**, **Sustainer Analog**, **Booster Analog**), with station-specific USB capture/recording, exclusive camera assignment, replay offsets and segmented FFmpeg recording. Each Away station exposes its two assigned receivers; Launch Video exposes only its local Digital camera. Its remote thumbnails support matching-channel promotion and show honest connection/age status; the station video transport is pending.
- Smooth articulated antenna graphics with orbit/zoom, including the grid reflector, Yagi and enclosed Avenger XR18 on a common beam. Physical and virtual pointers share the same manual controls and original shortcuts.
- Launch and antenna positions using latitude/longitude or MGRS; launch Plus Codes, URRG launch-pad preset (`18TUN2061530290`) and five station presets; launch-relative pointer heading, horizontal distance and altitude difference.
- OpenRocket trajectory simulation with bundled or selected team JAR, manual/imported/online wind, additional motors and reference comparison. Animated 3D playback shows attitude, recorded ignition/burnout events and parachute deployment. Older references without event/attitude columns remain usable; rerun them to add those details.
- Portable `.rktflight` Save/Open files (**⌘S / ⌘O**), mission/model/motor/reference/session storage, indexed replay, seek/speed controls and diagnostic events.
- **Settings…** (**⌘,**, or **Ctrl+,** on Windows) for the OpenRocket JAR, simulation time limit, recording folder and theme. Lucida Grande is bundled privately.

For hardware-free pointing rehearsal at an Away station, specify the antenna location in the mission, connect **Virtual antenna pointer**, load or generate an OpenRocket reference and start **Follow trajectory**. Simulation is a nominal reference; the legacy Zephyrus protocol does not provide the proposed vehicle's complete canard/tab feedback. Those channels remain unavailable until real feedback is integrated.

## Develop and build

From this directory, with Python 3.12, GNU Make and JDK 17+:

```sh
make setup PYTHON=python3.12
make run                 # Startup wizard; remembering choices is optional
make away                # Wizard preselects Away 1 / Telemetry
make video VEHICLE=iris   # Wizard preselects Away 1 / Video / Iris
make demo STATION=launch   # Recorded Zephyrus rehearsal
make test
make lint
```

Preselect all wizard choices from the command line, or add `--skip-setup` to open that workspace directly:

```sh
.venv/bin/python -m rocket_gnc_monitor --site away3 --role telemetry --vehicle iris --launch-site urrg --skip-setup
# Packaged Mac app, run from this directory:
dist/RocketGNCMonitor-v0a.app/Contents/MacOS/RocketGNCMonitor-v0a --site away3 --role telemetry --vehicle iris --launch-site urrg --skip-setup
```

Use `--site launch|away1|away2|away3|away4`, `--role telemetry|video`, `--vehicle balius|iris` and `--launch-site urrg|custom`. The old `base` argument remains an alias for `launch`. Omitted choices use the startup defaults, or the profile you explicitly chose to remember. `--skip-setup` leaves that preference unchanged unless you also pass `--remember-setup` or `--no-remember-setup`. See the [startup guide](docs/V0A_STATION_MODES.md#startup-wizard) for details.

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

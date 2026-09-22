# v0a station workspaces and ground-station connections

v0a organizes the monitor by station and operator role. One Base station and four numbered Away stations each offer Telemetry or Video. Balius has two system video channels; Iris has three, distributed across the stations.

## Startup wizard

Every normal launch asks for:

1. **Station**: Base / launch site, or Away 1, 2, 3 or 4.
2. **Role**: Telemetry or Video.
3. **Vehicle**: Balius (Digital + Analog) or Iris (Sustainer Digital + Sustainer Analog + Booster Analog).

The previous choices are remembered in `station-profile.json` in the application data directory. Cancel exits before any device controller is constructed. Finish opens the chosen workspace in LIVE with devices disconnected. The selected identity appears at the top of the window and remains fixed for that session; relaunch to change it.

**Base / Telemetry** opens Flight and Systems windows sharing one mission and controller. Put one on each display. Both windows can be moved and resized on a single display for preparation. The second window creates no duplicate serial workers or recording sessions.

**Away / Telemetry** opens one reduced workspace with main rocket telemetry and antenna pointing.

**Away / Video** opens one simplified window with its two assigned USB camera inputs. **Base / Video** shows the primary channels and all four Away stations below them; Base has only a local Digital USB camera.

Video does not appear in either telemetry workspace. The video operator does not need to connect a telemetry PCB or pointer board.

`make run` opens the wizard with remembered choices; `make away` preselects Away 1 / Telemetry; `make video VEHICLE=iris` preselects Away 1 / Video / Iris. For unattended development, for example:

```sh
.venv/bin/python -m rocket_gnc_monitor --site away3 --role video --vehicle iris --skip-setup
```

`--site` accepts `base`, `away1`, `away2`, `away3`, `away4`; `--role` accepts `telemetry`, `video`; `--vehicle` accepts `balius`, `iris`. Omit `--skip-setup` to review those choices in the wizard. The legacy `--station base|away|video` preselects Base Telemetry, Away 1 Telemetry or Away 1 Video; it does not bypass setup. Smoke-test flags bypass setup, except the dedicated controller-free `--setup-smoke`.

Station layout and data mode are separate decisions:

| Data mode | Input and behavior |
| --- | --- |
| LIVE | Physical connections start closed. Connect the desired ground-station board, pointer and cameras explicitly. |
| DEMO | Bundled GS1/GS2/GS3 Zephyrus recordings; no physical telemetry connection is needed. |
| REPLAY | A saved flight/session, with playback controls and physical command isolation. |

## Base station: Flight display

The flight display groups the information used to watch and control the rocket and maintain antenna pointing:

- Main telemetry, state, freshness and ground-station/rocket link status.
- Flight plots, reference trajectory and 3D rocket presentation.
- Antenna connection, current/commanded angles, articulated visualization, manual pointing and trajectory following.
- Three-axis GNC plots and all actuator channels in a side-by-side matrix.

The antenna and flight renderers animate independently of telemetry arrival. Drag the graphics to orbit, scroll to zoom and use the displayed view controls to restore the camera. The rocket's motor plume follows ignition/burnout events; its parachute appears only if the loaded simulation contains a deployment event. Reference attitude, measured telemetry and path-aligned illustrations are labelled so an illustration is not mistaken for sensor feedback.

## Base station: Systems display

The companion display exposes the supporting information and controls:

- Full rocket telemetry/GPS, servo and cell readouts, rocket commands, power rails, BMS protections and recovery controls supplied by the Zephyrus wire contract.
- Mission launch and antenna positions, OpenRocket configuration/reference and wind information.
- APRS/network connections and status.
- Session recording/replay and diagnostic events.

Monitoring information stays visible across the two windows. Configuration editors, confirmation dialogs and file selectors remain deliberate actions. Legacy functions retain their meaning even when their controls move to a different section.

The target layout is two 1920 × 1080 displays (about 1920 × 1020 usable window space). Fixed instrument tables show every normal channel/field; long event history, raw JSON and arbitrary-length wind profiles scroll inside their visible panels. **View → Arrange station displays** places each window on an available screen. With one screen, both base windows remain available for preparation; Away and Video modes each use one window. Closing the Flight window shuts down the entire workspace. The Systems close button keeps the required base display open and points to the single-window station modes instead. Shortcuts work from either display.

## Video role

### Away station

Both assigned channels remain visible together. Balius uses **Digital + Analog** at every Away station. Iris uses **Sustainer Digital + Sustainer Analog** at Away 1–3, and **Sustainer Digital + Booster Analog** at Away 4. Each has its own camera selector, **Find**, **Start**, **Stop**, local video **File…** input and capture status. A camera selected or in use by one channel is excluded from every other channel, including while a previous capture is still closing. No telemetry or pointer board connection is required.

### Base station

Two or three large primary channels sit above all four Away stations. There are eight thumbnail slots for either vehicle: each station contributes its assigned Digital/Analog pair. Iris’s large panes are Sustainer Digital, Sustainer Analog and Booster Analog; the Booster thumbnail exists only under Away 4. Base exposes one local USB camera selector, for **Digital** only. Digital initially shows that local source; Balius Analog and Iris Sustainer Analog initially select Away 1; Iris Booster Analog initially selects Away 4.

**Double-click any Away thumbnail** to replace its matching large channel. For example, Away 3 Sustainer Analog replaces only the large Sustainer Analog view. Away 4 Booster Analog replaces only Booster Analog. Digital promotion replaces only Digital. Every other thumbnail stays visible, including lower-quality alternatives. **Use local Digital** returns the large Digital view to Base's USB receiver; promotion never closes that camera.

The inter-station video connection has not yet been specified or implemented. Remote views therefore start with **Awaiting station link**, not simulated live pictures. Their presentation API already supports quality text, receive age, stale frames and loss of connection. Choosing a thumbnail selects its source even when it has no frame; it does not establish a network connection. The existing telemetry LAN feature does not carry video. Remote pictures injected through the future transport are display-only today; remote recording/replay is not implemented.

The supplied routing diagram applies to **Balius**: direct Digital reception and telemetry at Base and all Away stations, Analog reception only at Away stations, and Away-to-Base relay of video/telemetry with bidirectional comms. The [Iris diagram](../references/IRIS_STATION_ROUTING.png) adds stage-specific routing, summarized below. The stage names label receiver assignments; the application does not infer a vehicle identity from legacy telemetry packets.

### Recording and playback

The simplified screen hides serial connections, rocket readouts, antenna controls and mission panels. The data source remains visible so LIVE, generated DEMO video and recorded REPLAY are distinguishable. Local USB channels retain independent capture, segmented recording and replay. Once frames arrive, **Start recording** can create a video-only session. In REPLAY, a compact footer exposes flight/session loading, play, pause, seek and speed. Base replays the local Digital channel from an archive; inactive analog recordings remain preserved in the archive.

Settings remain available with **⌘,** / **Ctrl+,**. Quitting closes active workers. Normal station profiles are fixed for the session; the legacy programmatic layout-switching API retains its connection-preserving behavior for existing integrations.

## Iris receiver assignments

| Station | Local video receivers | Telemetry assignment | APRS assignment |
| --- | --- | --- | --- |
| Away 1–3 | Sustainer Digital; Sustainer Analog | Sustainer | Sustainer |
| Away 4 | Sustainer Digital; Booster Analog | Booster | Booster |
| Base / launch site | Sustainer Digital | Sustainer and Booster | Relayed from Away stations |

The wizard and station header identify the telemetry assignment. There is one downlink board per station; the downlink board selects one Iris stage at a time. Base additionally has a separate uplink board, also with an Iris target switch. The switch commands and acknowledgement are not defined; the application does not claim to know the physical target. APRS remains one external Dire Wolf KISS input with an optional callsign filter; set the appropriate vehicle callsign. Automatic stage identification and Away-to-Base APRS relay are not yet implemented. This does not change the existing read-only one-peer telemetry LAN or establish the planned multi-station data/comms transport.

## Iris target switches (placeholder)

The Iris Telemetry workspace displays a **Downlink receiver** target selector. Base also displays an independent **Uplink transmitter** target selector; Away stations have no uplink board or transmit controls. Both offer Sustainer and Booster. Initial desired choices follow the station assignment (Booster at Away 4, Sustainer elsewhere).

These are explicitly marked **PLACEHOLDER** because the firmware switch command and acknowledgement are not defined. A dropdown is only a desired target, never a confirmed hardware target. In LIVE and REPLAY, the hardware target remains unknown and switch actions are disabled. No target-switch bytes are invented or transmitted. Iris live rocket commands are also unavailable until the uplink target protocol is implemented.

In DEMO, **Simulate switch** updates the indicated simulated target and records an event identifying the downlink/uplink board and desired target. The two Base simulations are independent. Simulation changes switch state only: it does not relabel or replace the single bundled Zephyrus telemetry recording, and it does not transmit commands. Leaving DEMO clears simulated switch state. This supports interface rehearsal while the firmware contract is being finalized.

## Ground-station circuit-board mapping

The supplied ground-station software block diagram describes distinct data paths. USB device selection does not identify devices automatically by their cable position; use the port/camera names and verify each physical unit during setup.

| Hardware/data path | Monitor integration |
| --- | --- |
| Downlink telemetry board → USB serial | Present at Base and every Away station. Zephyrus receive/polling. A USB connection and recent valid rocket telemetry are separate status conditions. |
| Uplink telemetry board → USB serial | Base only. Existing Zephyrus command packets use this separate connection; Away stations cannot transmit rocket commands. |
| Antenna pointer board → USB serial | Independent pointer commands. Once a serial port is connected to any board, it disappears from every other board's available ports. |
| Digital video receiver → USB camera capture | Digital video channel. |
| Analog video receiver → USB camera capture | Away-only Analog channel (Sustainer at Iris Away 1–3, Booster at Iris Away 4). A camera selected for one channel is excluded from all other active selectors. |
| APRS radio audio → computer audio/Dire Wolf → KISS TCP | Receive-only uncompressed APRS positions from an external Dire Wolf decoder, default `127.0.0.1:8001`. |
| AP and LTU network equipment | Explicit read-only station status/telemetry exchange over the local LAN, default TCP `8765`. LTU management readings require its equipment protocol. |

The Digital/Analog names refer to the rocket-to-ground radio video paths, not to the computer input type: the local computer inputs are USB cameras. The video computer can capture either feed without connecting the telemetry board. Once frames arrive, the recording control can create a video-only recording; the absence of a telemetry board does not prevent this. Balius rocket commands require the Base uplink connection; downlink reception and polling remain independent. Iris live commands stay locked while its physical uplink target cannot be established by a defined switch protocol.

Unknown analog VRX control protocols and equipment-management interfaces are not represented as working controls or fabricated telemetry. An unavailable/unsupported status means the monitor has no verified value or command contract for that function. The current supported Zephyrus commands remain usable.

The [source diagram and implementation notes](../references/GROUND_STATION_BOARD_NOTES.md) record what is supported and which suggestions still require device protocols or additional work. Online wind retrieval needs internet access; manual and imported wind remain available offline.

## APRS and station LAN

The **Station network** panel keeps the two connections separate from the serial boards and USB video.

For APRS, run Dire Wolf externally with the radio audio input configured and KISS TCP enabled. Set its host and port in the APRS row (defaults `127.0.0.1`, `8001`), optionally enter a complete callsign including SSID, and choose **Connect**. A blank filter shows the latest supported position from any station. The panel shows connection state, callsign, latitude/longitude, optional altitude and age. Unsupported packets do not become positions.

The decoder accepts AX.25 UI uncompressed APRS positions (`!`, `=`, `/`, `@`); compressed positions, Mic-E, objects, NMEA and ambiguous positions are not supported. APRS `/A=` altitude is converted from feet to metres, but its datum is not inferred. APRS fixes are read-only recovery information; they do not replace flight telemetry or actuate the antenna. Dire Wolf itself is not bundled or configured by the monitor, and the monitor never transmits APRS.

For a local station link:

1. Join both computers to the ground-station AP/LTU network.
2. On one computer, set the LAN port (default `8765`) and choose **Listen**. The listener binds all local IPv4 interfaces and accepts one peer.
3. On the other computer, enter the listening computer's LAN IP and matching port, then choose **Connect**.
4. Check the peer's displayed station name, source mode, rocket-link state, altitude, phase and sample age. Choose **Stop** to close the connection.

Both sides exchange bounded, versioned, read-only snapshots about twice per second. Snapshot data includes selected telemetry, pointer state, link states and an available APRS fix; the panel shows a compact peer summary. Remote data stays separate from local telemetry and cannot enable or issue rocket/pointer commands. The link carries no video, audio or calling service. It is a direct local TCP connection and does not require an internet service.

Host/port/filter choices are stored in `station_network.json` in the application data directory. Connections always start off on a new launch and are closed when the workspace exits. A disconnected APRS fix is labelled as the last fix, and disconnected peer data is removed rather than being presented as live.

## Mission and antenna positions

The mission stores launch and antenna locations for simulation and virtual rehearsal. Physical Zephyrus tracking retains the legacy frozen ground-receiver GPS convention and Send to AntPtr action. Launch entry accepts decimal latitude/longitude, MGRS or Plus Codes, with URRG as a preset. Antenna entry accepts decimal latitude/longitude, MGRS or a position relative to launch.

For relative entry, specify the heading **from the antenna to the rocket at launch**, horizontal distance and altitude difference using the signs shown in the editor. Check the resolved coordinates before following a trajectory. Save the mission in a `.rktflight` file to preserve the model, motors, reference and available recording with it.

To rehearse without hardware: load or simulate a reference, select the virtual pointer, connect it and choose Follow trajectory. Manual pointer controls and the original keyboard shortcuts also operate the virtual mount. No physical pointer feedback is implied by the model: legacy firmware does not acknowledge moves or report measured pose.

## Developer integration

`station_profile.py` owns the immutable `StationProfile` and its validated, atomic JSON persistence. `startup_wizard.py` is a controller-free Qt wizard; `__main__.py` resolves saved/CLI defaults and waits for acceptance before constructing `StationWindow`. Smoke flags bypass interactive setup, while `--setup-smoke` only renders the wizard.

`station_workspace.py` assembles the role-specific cards over one inherited instrument owner. An explicit profile fixes identity and role for the window lifetime. Video role gates hidden serial menu actions and connection callbacks; it keeps recording shortcuts and file/replay controls. Telemetry retains the original shortcuts and device gating. The legacy constructor without an explicit profile supports prior layout-switching integrations.

`controller.py` accepts a `board_layout` (`legacy`, `base`, `away`) and vehicle profile. Base creates separate downlink/uplink/pointer workers; Away creates downlink/pointer workers. The legacy default preserves the previous combined ground-board API. Command readiness is separate from downlink reception readiness, and Iris live commands remain gated until its target-switch protocol exists. `iris_link_panel.py` owns clearly labelled DEMO-only target-switch state and never calls a transport.

`controller.py` also accepts an immutable `video_channels` tuple. Its per-channel states drive worker lifecycle, reservations, recording and replay; `ui.py` constructs matching local controls from `video_labels`. Unknown/inactive channels are rejected. Existing two-channel defaults and missing-stream-as-Digital recordings remain compatible. `recording.py` and `flight.py` preserve arbitrary channel directories without an archive schema change. Digital-only replay filters inactive channels without deleting their archived assets.

`video_wall.py` uses `StationProfile.away_channels` to validate every remote station/channel combination; unsupported combinations are rejected. It owns presentation and source selection only. A future transport should deliver decoded frames on the Qt GUI thread through `update_remote_frame(station, channel, QPixmap, quality="", received=None)`. Station IDs are `away1`–`away4`; channels are `digital`, `analog`, and Iris-only `analog2`. `received`, when supplied, must be local monotonic receive time. Use `mark_remote_unavailable(...)` on link loss. Five seconds without a fresh frame is labelled stale; quality strings are transport-provided and not inferred from image appearance. `set_local_source(label, live=False)` supplies truthful local demo/file/replay context and avoids falsely ageing paused recordings as a stale live camera. `select_remote(...)` promotes the matching channel, and `select_local_digital()` restores Base USB. `set_local_frame(...)` updates local Digital without overwriting a promoted remote view.

The wall starts no network workers. It does not subscribe to the existing telemetry LAN protocol, relay frames, record remote frames or claim a live receiver connection. Add the transport and its recording semantics after the station interface is specified. Tests exercise source promotion, stale state, image aspect ratio, channel exclusivity, all three local recordings, profile validation, wizard cancellation and role isolation.

## Deployment alongside v0

The Mac application is `RocketGNCMonitor-v0a.app`, bundle identifier `edu.mit.rocketteam.gncmonitor.v0a`, version `0.1.1`. It can coexist with the original v0 application and keeps separate preferences. The Windows executable/package has the same `-v0a` suffix. Keep the full app/package together; do not extract and move only its executable.

Packages target macOS 14 or newer (Apple Silicon and Intel in the universal distribution) and Windows x64. Intel execution is checked through Rosetta on Apple Silicon; the Windows build is checked in the supplied Windows 11 ARM VM using x64 emulation. These checks do not establish physical Intel/Windows hardware or receiver compatibility. The operator controls and original keyboard shortcuts should be checked with the connected equipment before field use. See the [universal build guide](MAC_UNIVERSAL.md) and the release validation record for platform details.

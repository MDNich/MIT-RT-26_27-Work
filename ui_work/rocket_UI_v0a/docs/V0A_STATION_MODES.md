# v0a station workspaces and ground-station connections

v0a reorganizes the monitor around the operator's station. The earlier monitoring pages remain available together in the base workspace, rather than being hidden behind the left navigation. A separate away layout reduces the workspace to the information needed at the antenna.

## Choose a station

**Base station** is the default. It opens a Flight window and a Systems window sharing one mission and controller. Put one on each display. Window placement uses available displays; both windows can also be moved and resized on a single display for preparation. There are no duplicate serial workers, video devices or recording sessions behind the second window.

**Away station** opens one reduced workspace with main rocket telemetry and antenna pointing. It is useful for an operator concentrating on antenna alignment and rocket position rather than managing the complete base station.

The command-line selectors are `--station base` and `--station away`. Development shortcuts are `make run` and `make away`. `make demo STATION=away` opens the recorded rehearsal in the away layout.

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

- **Digital video** and **Analog video**, both acquired from separate USB capture devices.
- Full rocket telemetry/GPS, servo and cell readouts, rocket commands, power rails, BMS protections and recovery controls supplied by the Zephyrus wire contract.
- Mission launch and antenna positions, OpenRocket configuration/reference and wind information.
- APRS/network connections and status.
- Session recording/replay and diagnostic events.

Monitoring information stays visible across the two windows. Configuration editors, confirmation dialogs and file selectors remain deliberate actions. Legacy functions retain their meaning even when their controls move to a different section.

The target layout is two 1920 × 1080 displays (about 1920 × 1020 usable window space). Fixed instrument tables show every normal channel/field; long event history, raw JSON and arbitrary-length wind profiles scroll inside their visible panels. **View → Arrange station displays** places each window on an available screen. With one screen, both base windows remain available for preparation; Away mode is the single-window operating layout. Closing the Flight window shuts down the entire workspace. The Systems close button keeps the required base display open and points to Away mode instead. Shortcuts work from either display.

## Ground-station circuit-board mapping

The supplied ground-station software block diagram describes distinct data paths. USB device selection does not identify devices automatically by their cable position; use the port/camera names and verify each physical unit during setup.

| Hardware/data path | Monitor integration |
| --- | --- |
| Ground-station telemetry board → USB serial | Zephyrus telemetry/commands. A USB connection and recent valid rocket telemetry are separate status conditions. |
| Antenna pointer board → USB serial | Independent pointer commands. Once a serial port is connected to either board, it disappears from the other board's available ports. |
| Digital video receiver → USB camera capture | Digital video channel. |
| Analog video receiver → USB camera capture | Analog video channel. A camera selected for one channel is excluded from the other channel's selector. |
| APRS radio audio → computer audio/Dire Wolf → KISS TCP | Receive-only uncompressed APRS positions from an external Dire Wolf decoder, default `127.0.0.1:8001`. |
| AP and LTU network equipment | Explicit read-only station status/telemetry exchange over the local LAN, default TCP `8765`. LTU management readings require its equipment protocol. |

The Digital/Analog names refer to the rocket-to-ground radio video paths, not to the computer input type: both computer inputs are USB cameras. The video computer can capture either feed without connecting the telemetry board. Once frames arrive, Start Logging can create a video-only recording; the absence of a telemetry board does not prevent this. Rocket command controls remain locked until their own serial connection is made.

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

## Deployment alongside v0

The Mac application is `RocketGNCMonitor-v0a.app`, bundle identifier `edu.mit.rocketteam.gncmonitor.v0a`, version `0.1.1`. It can coexist with the original v0 application and keeps separate preferences. The Windows executable/package has the same `-v0a` suffix. Keep the full app/package together; do not extract and move only its executable.

Packages target macOS 14 or newer (Apple Silicon and Intel in the universal distribution) and Windows x64. Intel execution is checked through Rosetta on Apple Silicon; the Windows build is checked in the supplied Windows 11 ARM VM using x64 emulation. These checks do not establish physical Intel/Windows hardware or receiver compatibility. The operator controls and original keyboard shortcuts should be checked with the connected equipment before field use. See the [universal build guide](MAC_UNIVERSAL.md) and the release validation record for platform details.

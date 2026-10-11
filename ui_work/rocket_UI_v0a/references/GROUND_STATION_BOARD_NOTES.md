# Ground-station board layout: v0a implementation notes

Source: [Ground Station Software Block Diagram.pdf](Ground%20Station%20Software%20Block%20Diagram.pdf), supplied by the user on September 22, 2026. The copy is byte-for-byte identical to the supplied PDF (SHA-256 `8685ef20c10e04ab3431a1737633fbc7a0a61eef363b93211ab654c8cf09f5aa`). The diagram is project reference material; its suggestions are not evidence that a hardware protocol has been supplied or a feature implemented.

## Physical paths described by the diagram

- The telemetry computer receives APRS audio and connects to the telemetry PCB and antenna-pointer PCB through separate USB interfaces.
- Radio audio is decoded by Dire Wolf on a computer; the monitor receives decoded APRS frames through KISS TCP.
- The video computer receives Digital VRX and Analog VRX feeds through USB. The diagram states that the analog VRX can also be controlled over USB, but does not define that command interface.
- The two computers join the access point over Wi-Fi. The access point connects to an LTU-XR over Ethernet.
- Inter-station operation should work on the local network without internet access. The diagram suggests LTU signal-strength/status display and audio/video calling as desirable additions.

## Implemented in v0a

| Area | Actual application behavior |
| --- | --- |
| Base station UX | Two coordinated windows expose the flight/antenna/GNC and video/support information without the former navigation tabs. Both windows share one local controller. |
| Away station UX | A reduced single-window layout concentrates on main rocket telemetry and antenna operation. Station layout is independent of LIVE/DEMO/REPLAY. |
| Telemetry and pointer PCBs | Independent Zephyrus serial connections and existing command/shortcut behavior. A connected port is excluded from the other board's selector. Ground-board USB connectivity and receipt of rocket telemetry are shown separately. |
| Digital and Analog VRX video | Independent USB-camera capture, device exclusivity, display and recording. Camera capture does not require the telemetry board. Video-only recording is available after frames arrive. |
| APRS | Receive-only KISS TCP client for an externally running Dire Wolf decoder; default `127.0.0.1:8001`, configurable host/port and exact callsign/SSID filter. Uncompressed AX.25 UI positions are displayed with age and optional altitude. |
| Local station sharing | Explicit Listen/Connect controls on configurable TCP port `8765`, one peer at a time, read-only snapshots about twice per second. The panel shows peer identity, mode, rocket link, altitude, phase and age. Selected telemetry, pointer and APRS data are carried in the versioned snapshot. |
| Offline operation | Serial, USB capture, the APRS decoder connection, station TCP sharing, recorded data, manual/imported wind and bundled OpenRocket run without an internet service. Online wind retrieval and build-time downloads still require internet access. |
| Connection lifecycle | Network settings persist locally, but connections do not start automatically. Closing the workspace stops the network workers. |

## Unsupported or deferred suggestions

- **LTU-XR signal strength and management:** no verified management interface, credentials, units or polling contract were supplied. The UI identifies this as requiring the equipment protocol; it does not invent metrics or make undocumented requests.
- **Analog VRX tuning/control over USB:** camera capture is implemented; receiver tuning is not. The receiver model and control protocol are needed to implement it.
- **Audio/video calls between stations:** not implemented. The station TCP protocol carries display data only, with no media or call signaling.
- **Video relay between computers:** USB video remains local to the computer that captures it. The read-only station link does not stream either feed.
- **Remote rocket or pointer control:** station sharing never forwards hardware commands or promotes peer telemetry into the local control path. Local command connection checks still apply.
- **Bundled Dire Wolf/audio setup:** Dire Wolf must be installed, configured and started externally. The monitor does not select an audio device or configure its modem.
- **Other APRS encodings:** compressed positions, Mic-E, objects, NMEA and ambiguous-space positions are rejected. The supported uncompressed position types are `!`, `=`, `/` and `@`. APRS altitude does not drive antenna motion.
- **LTU/AP configuration or multi-peer discovery:** the operating system/equipment supplies the LAN; peer IP/port selection is explicit. One LAN peer is supported at a time.

The two-display base layout is one application process. A separate video computer can run its own copy to capture its attached cameras without a telemetry-board connection; this does not make those camera frames appear remotely. Physical PCB, receiver, APRS-radio and LTU/AP acceptance remain equipment tests, separate from automated decoder/network/UI tests.

See [Station modes and operator setup](../docs/V0A_STATION_MODES.md) for the connection sequence and [Wire contract](../docs/PROTOCOL.md) for the supported Zephyrus serial commands.

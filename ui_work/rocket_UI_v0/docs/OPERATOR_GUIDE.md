# Operator guide

Lucida Grande Regular/Bold is included in the application package and loaded privately on every platform. No font installation is needed.

## Startup and connection control

Launch opens LIVE on the Control panel, with no automatic serial connection or camera capture. The three indicators separate computer-to-ground-board USB, rocket-to-ground radio reception, and computer-to-pointer USB. Ground board connected means its serial port opened. Rocket telemetry live means a checksum-valid LIVE packet arrived within the mission's freshness limit; no valid packet yet shows Waiting, and expired reception shows Lost / stale. The protocol has no separate radio handshake. Reconnecting the ground board requires a new packet before the radio can be shown live.

Connect each board independently at 115200 baud. Connecting the ground board opens its port; click **Start Polling** to receive telemetry. **Stop Polling** pauses reception while leaving the serial port and rocket commands available. **Start Logging** creates a session immediately. Ground commands/logging require the ground board; manual pointer controls require the pointer board independently. The control panel distinguishes connected/polling stopped, waiting, live reception, and stale reception.

## Original keyboard shortcuts

All shortcuts work from every workspace. On Mac, Qt maps Ctrl to **Command** and Alt to **Option**, as in the previous UI.

| Action | Windows / portable Qt | Mac |
|---|---|---|
| Refresh serial ports | Ctrl+R | ⌘R |
| Ground station connect/disconnect | Ctrl+Alt+C | ⌘⌥C |
| Antenna connect/disconnect | Shift+Ctrl+Alt+C | ⇧⌘⌥C |
| Start/stop polling | Ctrl+Return | ⌘Return |
| Start/stop logging | Ctrl+L | ⌘L |
| Pointer UP / DOWN / RIGHT / LEFT | Ctrl+arrow | ⌘arrow |
| Pointer ZERO | Ctrl+0 | ⌘0 |

The Serial controls menu shows the shortcuts and current toggle state. Each action follows its board's connection state.

## Rocket controls

Open **Rocket controls** for the complete legacy telemetry/GPS/servo/cell tables, state and zero commands, roll and airbrake angles, PD Activate, VTX 1/3/5/8 W, power rail requests and readbacks, BMS status, six pyro channels, and emergency recovery commands. The 3.3 V request stays on, matching the previous UI; Total is an aggregate indicator. State advance, pyro ARM/FIRE, and emergency recovery retain their confirmation dialogs. Pyro actions require selecting channels 0–5. Radio freshness is displayed independently from the ground serial connection.

## Rehearse

Choose **DEMO** explicitly (or run `make demo`) to play the actual Zephyrus test launch. **GS2** is the default receiver log; select **GS1** or **GS3** in the playback strip. The logs remain independent, preserving each receiver's timing, gaps, packet numbers, UTC timestamps and measurements. All three are bundled for offline use. No serial transport opens in DEMO and all operator commands are simulated.

Playback begins **five seconds before the first recorded FLIGHT state**. Use Pause/Play, the timeline, 0.25×–4× speed, **Launch −5s**, or **Full start** to review the complete recording. Seeking reconstructs the recorded history up to that point. Playback stops at the final received sample; these recordings end during MAIN descent and do not contain touchdown. Starting again returns to the launch cue. Stop logging before changing recordings or seeking; pause and speed changes are allowed during logging. Returning to LIVE clears demo data and retains the configured mission and previous reference.

The track uses recorded GPS horizontal offsets from the launch transition and the reported barometric altitude. This local display frame is not a surveyed altitude datum or simulated prediction. Samples without a 3D fix, or more than 20 km from launch, are omitted from the track and identified in the banner; their original values remain in telemetry and Diagnostics. GS1/GS3 contain corrupt GPS readings. GS3 has no valid receiver GPS, so automatic pointer tracking is unavailable for that log. GS1/GS2 can rehearse pointing using recorded receiver coordinates and the original barometric-height calculation.

Four recorded legacy servo drives appear; new canard/tab feedback remains unavailable. Zero-valued battery readings, state anomalies, and other original data are retained. The video is explicitly labeled **VIDEO TEST PATTERN**; no launch video was supplied. Demo session recordings retain source filename/hash, original UTC and row text, all 43 legacy fields, and simulated-command events. Raw radio bytes/checksums are unavailable for these decoded CSVs.

View → Daylight theme changes contrast. Choose plan, side or projected perspective for the track. Imported simulation references show a dashed trace and same-time marker. The legacy attitude instrument displays integrated rotations, not a qualified navigation estimate. Dataset provenance and quality notes: [DEMO_DATA.md](DEMO_DATA.md).

## Configure and connect

Mission → Configure: choose **Latitude / longitude**, **MGRS**, or **Plus Code** for the launch location. All conversions work offline and display the resolved WGS84 coordinates before Save. MGRS accepts compact or spaced references, UTM and polar grids, and reports the supplied grid resolution; it uses the grid reference point. Full Plus Codes resolve directly to their area center. For a short Plus Code, enter nearby reference latitude/longitude; a named locality alone is not resolved. Saving retains the chosen format and code alongside canonical latitude/longitude. Switching formats alone preserves the existing coordinates.

Enter WGS84 **ellipsoid altitude**, separate **mean sea level elevation**, and mark the origin established. Geographic transforms use ellipsoid height; atmosphere/weather use MSL. Choose the verified legacy altitude interpretation. Firmware may zero GPS height preflight; select GPS relative to launch if that is the board configuration. This interpretation controls the trajectory comparison. Legacy pointer tracking continues to use its original GPS/barometric convention.

Stop recording before changing the mission. Legacy pointer operation does not require a mission-calibration checkbox.

In the default LIVE mode, assign the ground station and antenna board to different serial selectors, and connect each explicitly. Both are 115200 8N1, no flow control, with the same default DTR/RTS settings as the old UI. Rescan after plugging in devices. Reconnect manually; tracking never resumes automatically after a stale target/disconnect.

Find cameras → select USB receiver → Start camera. Grant OS camera permission. One input supplies both display and recording. Stop closes capture and labels the retained final frame. Video-file input is also available.

Flight t=0 is set only by an observed Preflight → Flight transition or an explicit operator alignment in Sessions. Joining mid-flight leaves it unaligned. Onboard time is uptime; after a detected reboot, realign it. Diagnostics shows packet counters, full samples and alerts. Low battery requires one second below threshold and clears 0.3 V above it. Acknowledgment logs an event without hiding the active condition.

## Antenna

The drawing follows the supplied stand and antenna references with the September 20 attachment clarification: the grid dish, Yagi and black Avenger XR18 mount directly to a shared beam concentric with the support pivots. Their mounting centers share the beam elevation rather than using raised/lowered stalks. Dimensions and hidden mechanisms are illustrative. Drag the model to orbit from any angle, including above and below; scroll to zoom; double-click or use a preset to reset the view. Orbit changes only the viewing camera, even when Live controls are locked. Enter azimuth/elevation and click Send. Editing the fields does not move the graphic or transmit. UP/DOWN/LEFT/RIGHT send the original firmware direction opcodes; ZERO sends the original zero opcode.

“Sent” means serial dispatch, not board acknowledgment or arrival. Measured angles are unavailable. “ZERO” resets software step counters at the physical current position; it does not home to a switch. The graphic follows the last sent target; a direction command before a known target leaves the angle readout unknown.

With both boards connected and polling, use **Send to AntPtr** to freeze the ground-station GPS coordinates. **Start tracking** then sends pointing angles at 5 Hz using the rocket GPS latitude/longitude and filtered barometric altitude, exactly as the old UI calculated them. Ground coordinates retain the old five-decimal rounding and the old pointer altitude of zero. The displayed receiver altitude retains its historical division by 1000. These conventions are preserved separately from trajectory display settings. Unfreeze to update the ground location; Stop tracking ends periodic commands. Stale/invalid telemetry or disconnection stops host tracking; restart explicitly.

**Stop tracking stops new targets and removes unsent queued work. The last commanded movement may continue.** An independent physical stop/power control is needed to interrupt motion. The legacy protocol supplies no stop/watchdog. No automatic retries. REPLAY cannot transmit.

## Wind and nominal reference

Set the site and a timezone-bearing weather time, e.g. `2026-09-18T16:00:00Z`. Retrieve weather or enter/import a manual profile, then Apply wind after table edits. Heights are metres above launch, directions meteorological **from** true north, speed m/s. Internally wind uses east/north vectors. Retrieved geopotential heights are converted to geometric MSL height then height above launch. The nearest available hour within one hour is used; outside layer coverage the nearest endpoint wind is held. Review coverage. Raw requests/responses are retained with missions/sessions for offline reuse. [Open-Meteo](https://open-meteo.com/en/docs) weather data is attributed under CC BY 4.0.

Select a `.ork` with a saved simulation/motor configuration; index 0 means the first saved simulation. Optional `.eng`/`.rse` motor resources are loaded in the isolated worker. Run nominal simulation; Cancel terminates its process without stopping telemetry.

The bridge uses the saved motor/flight configuration, specified rail/site/wind, ISA atmosphere, zero turbulence standard deviation, fixed seed and first output branch. Saved simulation extensions and the fork's global inertia override are disabled. Inspect `trajectory.json` warnings/branch count and `worker.log` in the job folder. Controlled canard/tab dynamics remain unqualified.

An imported normalized reference needs a CSV with `time_s,east_m,north_m,up_m` and same-basename JSON declaring `schema_version:1`, `frame:"ENU"`, `units:"m,s"`, `origin:[latitude,longitude,ellipsoid_altitude]`. Up is launch-relative. Live origins must match. No reference-time extrapolation is performed.

## Sessions

Start Logging (or ⌘L on Mac) immediately creates a unique folder under the application data directory’s `sessions` folder. Its path appears in Diagnostics. Each folder contains `telemetry.csv` and `telemetry_badpackets.csv` with all 43 original columns, plus the manifest, indexed SQLite telemetry/events, CRC-protected incoming/outgoing serial bytes, optional reference, and video segments. Stop Logging finalizes the session. The recorder operates independently of UI redraws. Closing finalizes recording; inspect completion/error status.

Open the folder in Sessions. Play/pause, seek, 0.1-second step and 0.25×–4× speed are available. Seek removes future state and restores earlier commands/time alignment. CSV export retains full sample JSON. Incomplete sessions may be read if committed SQLite data is intact and remain marked incomplete. Do not remove a crashed session's SQLite `-wal` file before recovery.

Video uses host timing, not exposure timestamps. A positive mission video offset delays video; a negative offset advances it. Paused seek decodes one frame. Reconnect creates a new segment directory. A crash may lose the active video segment and uncommitted telemetry while finalized data remain recoverable.

Import Zephyrus CSV converts the audited legacy monitor layout into a replay session, retaining the original file, extra columns and quality limitations. Other CSV layouts are rejected; raw packet checksums are unavailable for CSV imports. Serial reconnect is manual. New vehicle actuator feedback requires a new verified wire contract.

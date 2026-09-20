# Operator guide

## Startup and connection control

Launch opens LIVE on the Control panel, with no automatic serial connection or camera capture. The three indicators separate computer-to-ground-board USB, rocket-to-ground radio reception, and computer-to-pointer USB. Ground board connected means its serial port opened. Rocket telemetry live means a checksum-valid LIVE packet arrived within the mission's freshness limit; no valid packet yet shows Waiting, and expired reception shows Lost / stale. The protocol has no separate radio handshake. Reconnecting the ground board requires a new packet before the radio can be shown live.

Live camera/video starts and recording are locked until the ground board connects. Pointing, jogging and software zero additionally require the pointer board and mount calibration. Tracking also requires fresh valid position and the established cable route. Losing the ground connection relocks controls and clears unsent pointer commands. Stop/hold remain available when needed; an already running recording can continue to capture the interruption. Mission setup, camera discovery, file review, navigation and camera orbit remain available offline.

## Rehearse

Choose DEMO explicitly in the mode selector (or run `make demo`): fictional telemetry/actuators, a synthetic video test pattern and no physical transports. The fictional flight ends at 140 seconds; switch out of DEMO and back to restart. View → Daylight theme changes contrast. Flight plots show actual/demo track, dashed reference, and a gold marker at the same flight time. Choose plan, side or projected perspective. The legacy attitude instrument displays integrated rotations, not a qualified navigation estimate.

## Configure and connect

Mission → Configure: enter launch latitude/longitude, WGS84 **ellipsoid altitude**, separate **mean sea level elevation**, and mark the origin established. Geographic transforms use ellipsoid height; atmosphere/weather use MSL. Choose the verified legacy altitude interpretation. Firmware may zero GPS height preflight; select GPS relative to launch if that is the board configuration. Unknown blocks tracking. Receiver-board height has conflicting historical units and is not used as the mount origin.

Configure the antenna pivot separately, including board alignment offsets, elevation/azimuth envelope and physical reference. Calibration is never restored from saved files and is cleared after pointer reconnect. Stop recording before changing the mission.

In the default LIVE mode, assign the ground station and antenna board to different serial selectors, and connect each explicitly. Both are 115200 8N1, no flow control. Rescan after plugging in devices. Reconnect manually; tracking never resumes automatically after a stale target/disconnect.

Find cameras → select USB receiver → Start camera. Grant OS camera permission. One input supplies both display and recording. Stop closes capture and labels the retained final frame. Video-file input is also available.

Flight t=0 is set only by an observed Preflight → Flight transition or an explicit operator alignment in Sessions. Joining mid-flight leaves it unaligned. Onboard time is uptime; after a detected reboot, realign it. Diagnostics shows packet counters, full samples and alerts. Low battery requires one second below threshold and clears 0.3 V above it. Acknowledgment logs an event without hiding the active condition.

## Antenna

The drawing follows the supplied stand and antenna references with the September 20 attachment clarification: the grid dish, Yagi and black Avenger XR18 mount directly to a shared beam concentric with the support pivots. Their mounting centers share the beam elevation rather than using raised/lowered stalks. Dimensions and hidden mechanisms are illustrative. Drag the model to orbit from any angle, including above and below; scroll to zoom; double-click or use a preset to reset the view. Orbit changes only the viewing camera, even when Live controls are locked. Azimuth/elevation fields preview the commanded assembly pose. Point antenna sends an absolute target; 5° buttons step from the last sent target through the same checked absolute-command path.

“Sent” means serial dispatch, not board acknowledgment or arrival. Measured angles are unavailable. “Set current position as zero” resets software step counters at the physical current position; it does not home to a switch. Physically establish the configured reference first.

Track requires a fresh live position, 3D GPS fix, known altitude convention and a verified continuous azimuth cable route. The firmware chooses its own shortest route and reports no progress. Stale/invalid/out-of-envelope targets stop host scheduling. Restricted-envelope manual checks use the previous target and are advisory, not verified mechanical protection.

**Hold stops new targets and removes unsent queued work. The last commanded movement may continue.** An independent physical stop/power control is needed to interrupt motion. The legacy protocol supplies no stop/watchdog. No automatic retries. REPLAY cannot transmit.

## Wind and nominal reference

Set the site and a timezone-bearing weather time, e.g. `2026-09-18T16:00:00Z`. Retrieve weather or enter/import a manual profile, then Apply wind after table edits. Heights are metres above launch, directions meteorological **from** true north, speed m/s. Internally wind uses east/north vectors. Retrieved geopotential heights are converted to geometric MSL height then height above launch. The nearest available hour within one hour is used; outside layer coverage the nearest endpoint wind is held. Review coverage. Raw requests/responses are retained with missions/sessions for offline reuse. [Open-Meteo](https://open-meteo.com/en/docs) weather data is attributed under CC BY 4.0.

Select a `.ork` with a saved simulation/motor configuration; index 0 means the first saved simulation. Optional `.eng`/`.rse` motor resources are loaded in the isolated worker. Run nominal simulation; Cancel terminates its process without stopping telemetry.

The bridge uses the saved motor/flight configuration, specified rail/site/wind, ISA atmosphere, zero turbulence standard deviation, fixed seed and first output branch. Saved simulation extensions and the fork's global inertia override are disabled. Inspect `trajectory.json` warnings/branch count and `worker.log` in the job folder. Controlled canard/tab dynamics remain unqualified.

An imported normalized reference needs a CSV with `time_s,east_m,north_m,up_m` and same-basename JSON declaring `schema_version:1`, `frame:"ENU"`, `units:"m,s"`, `origin:[latitude,longitude,ellipsoid_altitude]`. Up is launch-relative. Live origins must match. No reference-time extrapolation is performed.

## Sessions

Record session → choose parent folder. A unique child contains manifest, indexed SQLite telemetry/events, CRC-protected raw serial bytes, optional reference, and video segments. The recorder operates independently of UI redraws. Closing finalizes recording; inspect completion/error status.

Open the folder in Sessions. Play/pause, seek, 0.1-second step and 0.25×–4× speed are available. Seek removes future state and restores earlier commands/time alignment. CSV export retains full sample JSON. Incomplete sessions may be read if committed SQLite data is intact and remain marked incomplete. Do not remove a crashed session's SQLite `-wal` file before recovery.

Video uses host timing, not exposure timestamps. A positive mission video offset delays video; a negative offset advances it. Paused seek decodes one frame. Reconnect creates a new segment directory. A crash may lose the active video segment and uncommitted telemetry while finalized data remain recoverable.

Import Zephyrus CSV converts the audited legacy monitor layout into a replay session, retaining the original file, extra columns and quality limitations. Other CSV layouts are rejected; raw packet checksums are unavailable for CSV imports. Serial reconnect is manual. New vehicle actuator feedback requires a new verified wire contract.

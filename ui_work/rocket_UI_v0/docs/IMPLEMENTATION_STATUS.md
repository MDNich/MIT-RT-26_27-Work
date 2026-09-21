# Implementation and acceptance status

## September 21 Mac revision — antenna location entry

- Antenna mission location accepts latitude/longitude, MGRS, or launch-relative true heading, horizontal distance and antenna-minus-launch altitude difference. The preview resolves WGS84 coordinates offline.
- MGRS format/code and relative parameters persist in mission JSON and portable flights; old files retain latitude/longitude defaults. Relative positions recalculate when the mission launch site changes.
- WGS84 tangent-frame solving preserves antenna-to-pad heading and horizontal range, with 0–100 km input validation. Cardinal, oblique, southern-hemisphere, high-latitude and antimeridian cases are covered.
- **107 regression tests passed**. Native Mac dark/daylight forms reviewed. Packaged verification exercises MGRS and relative positions through the flight-file workflow. Windows has not been rebuilt.

## September 21 Mac revision — virtual pointer and dropdown repair

- Mission configuration includes an Antenna pointer tab with a persistent WGS84 location and an explicit location-established flag.
- The virtual pointer connects independently in LIVE, decodes the legacy pointing/jog/ZERO commands, and animates an illustrative two-axis slew without a physical port.
- Georeferenced OpenRocket references drive a separate rehearsal clock with play/pause, seek, rewind and speed controls. Reference ENU positions are transformed through ECEF into the antenna's local frame. The plot distinguishes the virtual target and mount from telemetry.
- Manual input pauses rehearsal; Hold, mode/location/reference changes and disconnect stop simulation appropriately. Physical live tracking retains its legacy GPS workflow.
- Mac dropdowns use a styled popup with widths measured after font/style application. Native Cocoa inspection covers mode, projection, Settings, location, serial and long camera labels in both themes.
- **101 regression tests passed**; package verification includes virtual-pointer rehearsal. Windows has not been rebuilt for this revision.

## September 21 Mac revision — Digital and Analog video

- Flight overview contains two independent USB camera/file inputs labeled Digital and Analog, each with start/stop, frame age, errors and a bounded frame queue.
- Camera choices exclude the other panel's selection. Controller reservations also cover asynchronous opening and closing. Serial dropdowns omit ports used by the other board while connecting or connected, including macOS tty/cu aliases.
- Both feeds record and round-trip through portable flight files. Replay follows each stream's own starts, segments and gaps; old untagged recordings map to Digital. Closing logging waits for finalization of both feeds.
- DEMO supplies distinct labeled test patterns for both panels. It still uses the unchanged recorded Zephyrus telemetry.
- **77 regression tests passed** on Mac. The new checks exercise duplicate choices, closing reservations, independent failures/frames, legacy playback, dual-video flight round trips and minimum-size layout.
- macOS is the build target for this revision. Physical dual-USB-camera acceptance remains separate from the synthetic video and packaged checks.

## September 20 Mac revision — legacy feature parity

- All original operator functions and all ten keyboard shortcuts are restored. See [the complete inventory and reference tests](LEGACY_PARITY.md).
- Default launch is LIVE on the connection control panel. No automatic camera, telemetry polling, or physical serial connection.
- Ground and pointer connections operate independently, with the old serial settings. Start/Stop Polling is separate from connection. Rocket uplinks work with polling paused. Native pointer direction/ZERO packets match the original UI.
- Rocket controls contains all original telemetry, GPS, servo, cell, power, BMS, pyro, VTX, state/zero and emergency recovery controls. Original state/ARM/FIRE/recovery confirmations are retained.
- Start/Stop Logging immediately creates a session containing both original 43-column CSVs alongside raw serial/SQLite/video. Ground-GPS freeze and the original tracking calculation are restored.
- All antennas share the elevation beam through the support pivots. The feed arm uses the dish material and shares the dashed boresight axis. The compass uses a right-handed E/N/Up frame, with 90° azimuth pointing East. Camera orbit, zoom and reset remain independent of commands.
- Lucida Grande Regular/Bold is bundled for both platform builds and applied throughout widgets, plots, dialogs and antenna labels.
- Launch location accepts lat/lon, MGRS and Plus Codes offline. Short codes require a nearby reference; mission persistence retains entry format and canonical coordinates.
- URRG is a launch-site preset using the exact supplied MGRS `18TUN2061530290`; manual coordinate edits clear the preset name, and elevations remain explicit.
- Portable `.rktflight` files save/load mission, model/motors, reference, telemetry/raw/CSV/events and finalized video. Active logging snapshots use an online SQLite backup plus matching committed file prefixes; loading validates paths/checksums before switching to paused replay or disconnected planning. Tests cover removed original assets, running captures, final video, full-demo export, buffered-only telemetry, corrupt files and atomic failed saves.
- DEMO uses the exact GS1/GS2/GS3 Zephyrus test-flight CSVs, compressed losslessly and hashed. GS2 is default, with a five-second prelaunch cue, full-recording access, pause/seek/speed, original legacy readouts and source provenance. No fictional telemetry or actuator feedback is generated.
- Zephyrus `.ork` simulations automatically resolve the bundled MITRT N8406 curve by its exact engine digest. Missing curves/unpowered configurations produce named, actionable errors. The supplied unmodified model is checked through the packaged worker.
- **71 regression tests passed** on Mac, including 118 captured rocket-packet cases, all original shortcuts exercised through actual Qt key events, original decoder/CSV values, two pseudo-terminal connections, confirmation paths, and recording/replay. Python static checks passed.
- Minimum-size 1120×800 screens, all restored tabs and dark/daylight themes are checked. Mac package verification checks LIVE startup, all three bundled Zephyrus recordings with synthetic video, portable flight round trips with URRG, and the bundled OpenRocket worker with a minimal system PATH.
- Windows was not rebuilt for this revision. The following September 18 results describe the prior baseline. Actual board/camera/mount acceptance remains outstanding.

## Historical September 18 baseline

September 18, 2026. The folder contains an implemented desktop application; original planning files are retained as the design baseline.

Initial baseline implemented: native workspaces; independent Zephyrus connections; incremental decoding; USB/video-file capture; photo-informed articulated mount; guarded manual pointing/tracking/reference reset; normalized GNC channels with explicit legacy availability; manual/online wind; isolated nominal OpenRocket; raw/decoded/event/video recording; indexed replay and CSV export; diagnostics/alerts; native Makefiles and complete runtime packaging.

Automated tests cover corrupt/split frames, rollover/reboot, coordinate/datum handling, pointer encoding/envelopes, mode isolation, stale tracking, dispatch races, alerts, raw CRCs, incomplete recordings, replay state and bundled FFmpeg recording. A real OpenRocket example generated 1,551 rows; two independent jobs matched exactly. A live Open-Meteo request returned eight wind layers. 

Remaining field/release acceptance:

- Clean production-machine checks, including physical Windows x64 hardware. The supplied Windows 11 ARM VM has now passed an x64 package build and execution test under emulation.
- Actual two boards and USB receiver: identity assignment, baud, unplug/reconnect, camera modes/permissions, recording recovery.
- Physical mount calibration, cable route, signs/envelope and independent stop hardware. Legacy firmware cannot establish measured pose or confirmed stop.
- New board contract for three-axis GNC and actual canard/four-tab demands/feedback. Missing measurements cannot be inferred from four legacy drives.
- Controlled-vehicle aerodynamic/actuator model and force/moment/inertia qualification. Current bridge is nominal only.
- Launch-day-duration soak, representative hardware traffic, disk-full/power-loss drills and each supported OS/CPU.
- Signing/notarization and corresponding engine/dependency source redistribution materials.

Rocket uplink and pyro/recovery controls were added in the September 20 parity revision. Serial reconnection/tracking resumption are manual. The audited Zephyrus CSV layout has a tested converter; other layouts are rejected. Geometry is photo-informed, not surveyed CAD. Video synchronization uses host receipt plus manual offset, not exposure timestamps. Recovery cannot recreate uncommitted data/unfinalized video. Original source folders remain unchanged; application work is isolated under `rocket_UI_v0`.

## Local validation completed

- **31 tests passed** with Qt offscreen on macOS 26.5 arm64; static Python checks passed. Includes two simultaneous OS pseudo-serial ports, safe legacy CSV import, complete demo record/replay with paused video seek, asynchronous mode changes, and a 2,500-sample close/drain test. No physical serial device was opened.
- Native Qt workspace renders inspected at 1480×980, 1440×900 and 1120×800; antenna controls scroll vertically on smaller screens without horizontal clipping. Dark/daylight themes exercised.
- macOS `.app` and DMG compiled with bundled Python/Qt, FFmpeg, Temurin Java17 and the supplied OpenRocket engine. Mac code-signature integrity verified using deep/strict validation. The signature is ad hoc, not notarized.
- Standalone demo and simulation checks passed with PATH restricted to `/usr/bin:/bin`: decoded synthetic video and telemetry, no hardware transport, 1,551-point OpenRocket reference with 51.19043072 m apogee for the included small example. This is a dependency-isolation check on the development Mac, not a clean-machine certification.
- Two independent source-mode OpenRocket jobs produced identical numeric trajectory arrays. Live weather retrieval produced eight pressure-level wind layers.

Reports/logs are under `build/`; final artifacts and SHA-256 sidecars are under `dist/`. The machine-readable report in this documentation records the source/dependency context. Release archives are regenerated after code changes.

## Windows VM validation completed

- Windows 11 Pro 10.0.26200 ARM64 VM, with Python 3.13.14 x64 and Qt 6.11.2. **30 tests passed, 1 POSIX-only test skipped**, using the native Windows display driver. Static checks passed.
- Compiled the Java bridge with Windows JDK17, then built a Windows x64 executable (PE machine `0x8664`) and portable ZIP. Architecture selection follows the Python process, so x64 runtimes are bundled even on an ARM host.
- Extracted the ZIP to a Windows folder containing spaces and launched it as the logged-in user with only Windows system folders on PATH. The VM had no working internet access; build dependencies were staged through the Mac share.
- Standalone demo: 32 telemetry samples, 73 video frames, no physical transport. Private OpenRocket worker: 1,551 rows, 51.19043072 m apogee, matching the Mac example result.
- Confirmed the ZIP contains Python313, Qt's Windows plugin, Visual C++ runtimes, FFmpeg, Java, the OpenRocket engine/bridge and example model. The Windows executable is unsigned.

`make verify-package` now automates packaged demo/video and simulation checks on either OS; both platform `all` targets include this final check. Windows ARM execution is through x64 emulation, not a native ARM64 application build. Physical USB camera/serial-board qualification remains outstanding.

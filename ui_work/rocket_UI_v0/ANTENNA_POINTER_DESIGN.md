# Antenna pointer — interface and integration design

**September 20 implementation amendment:** the user's newer geometry instruction supersedes the original photo-based height assumptions below. All three antennas attach directly to the common beam through the support pivots; the Yagi and Avenger no longer use raised/lowered mounting stalks. The Mac renderer now supports full drag-to-orbit viewing, scroll zoom and preset/reset views. Live operating controls require a ground-board connection; physical pointer commands also require the calibrated pointer board. This supersedes the original independent manual-control policy. See `docs/OPERATOR_GUIDE.md` for current behavior; the remainder is the original planning record.

Planning addition: 18 September 2026. This extends the GNC-monitor plan to include two serial devices and active control of the ground antenna. It is a design specification, not a hardware-connected application.

## 1. Two boards, two independent connections

| Device role | Responsibility | Application behavior |
|---|---|---|
| Ground station board | Receive rocket telemetry and available receiver metadata | Decode/record telemetry; supply a valid live rocket target to tracking |
| Antenna pointer board | Execute azimuth/elevation motion commands and provide whatever status its firmware supports | Independent command queue, serial worker, connection state, command history, and feedback model |

Both devices are first-class entries in the connection panel and permanent status strip. Each has a port picker, connect/disconnect control, configured baud rate, device identity when available, and diagnostics. The legacy Python adapters both default to 115200 baud; confirm each with its board firmware.

Save roles by stable USB identity when possible, with the port path as a current address. Where hardware lacks a unique identity, require explicit role selection and show that identity is unverified. Do not identify a board by sending a movement command. Prevent simultaneous assignment of the same physical device to both roles.

The pointer can connect and support manual positioning without rocket telemetry. Ground station acquisition continues without the pointer. Live tracking requires valid data from both the rocket stream and the calibrated antenna configuration. Pointer disconnects, blocked writes, or invalid replies do not interrupt telemetry/video recording.

## 2. Visual direction

The Antenna workspace should feel like a clean instrument console, with the physical assembly as the dominant visual rather than a collection of arrow buttons.

Use an opaque charcoal/navy night surface and a daylight alternative, restrained teal highlighting for the selected pointing direction, warm highlighting for a preview/target, high-contrast numeric angles, and thin compass/grid marks. Avoid decorative gauges that imply measurements unavailable from the hardware. Pair every status color with a label.

### Physical model

Construct a lightweight articulated scene with these recognizable parts:

1. **Four fixed timber legs:** tall, splayed rectangular wooden members, small wooden foot blocks, and dark vertical ground stakes. These replace the initial short metal stand and remain fixed while pointing.
2. **Square platform and azimuth stage:** a thin square wooden deck above the legs, with the rotating upper assembly supported around the vertical axis. Hidden bearing geometry remains schematic.
3. **Elevation support:** a tall, box-shaped, pale gray/green support with broad side panels, a visible horizontal pivot, and the antenna carrier above it. This replaces the initial exposed metal yoke.
4. **Central grid reflector:** an open, approximately rectangular curved wire-grid dish with edge rails and a projecting feed arm. Preserve the visible gaps between wires; the photograph does not show a solid circular bowl.
5. **Overhead Yagi:** a very long slender boom with many transverse elements, raised on a dark mast and pale mounting housing. Its rear is above/to the right of the grid dish in the supplied view, with its boom projecting far to the left.
6. **Avenger XR18 below/left:** the user confirmed that the black unit below and to the left of the grid dish in the supplied photograph is the XR18. Use the [VAS product reference](https://www.videoaerialsystems.com/products/5-8ghz-avenger-xr-18dbi-rhcp) for its enclosed tapered housing and rear connector, and the mount photograph for its placement. The original exposed-coil placeholder has been replaced.

Use **Avenger XR18** as the component name. The [user's mount photograph](references/antenna-pointer-user-photo.png), together with the explicit component identification, is the primary reference for the assembly. Relative dimensions, hidden bracket details, and exact pivot offsets remain approximate.

For the photo-informed schematic, directional descriptions refer to the supplied reference view. The user's confirmation of the XR18 below/left of the grid dish supersedes the initial generic left/right description. Preserve each physical attachment as the camera orbits; a component must not swap sides merely to stay screen-left. The scene provisionally uses a common elevation carrier. The single photograph does not establish the entire linkage, calibrated antenna boresight offsets, or whether every accessory tilts together.

The scene graph is `fixed stand → azimuth turntable → elevation carrier → antenna components`. Camera orbit is separate from mount motion. Neither azimuth rotation nor elevation tilt should rotate the four feet. Hardware geometry lives in a vehicle/mount asset, not inside telemetry or motor logic.

Show a labelled compass floor ring, a boresight ray, optional target direction, and component labels. A command preview can use a translucent pose/ghost. The measured pose uses solid geometry only when actual angle feedback exists; otherwise the solid pose is explicitly labelled **Commanded pose — feedback unavailable**. Smooth animation indicates a UI transition, never evidence that the hardware followed it.

### Layout

```text
┌ ROCKET GNC / ANTENNA ────────────────────────────────────────────────────┐
│ Ground station: port + state       Pointer: port + state      LIVE/DEMO │
├──────────────────────────────────────────────┬──────────────────────────┤
│ ANTENNA ASSEMBLY                             │ POINTING                 │
│                                            │ Mode: Manual / Track     │
│          dish + long Yagi + XR18             │ Azimuth / elevation      │
│              elevation carrier              │ requested / sent / actual│
│             azimuth turntable               │                          │
│              four-legged stand              │ Preview → Point          │
│                                            │ Jog · Hold tracking      │
│ compass floor / boresight / target ghost     │ Origin / alignment       │
├──────────────────────────────────────────────┴──────────────────────────┤
│ Target source + age · geometry validity · pointing error if measurable  │
│ Command / feedback timeline                                            │
└─────────────────────────────────────────────────────────────────────────┘
```

Provide perspective, front, and side viewpoints, optional component labels, and a compact inset on the flight overview. A 2D compass plus elevation side silhouette provides a functional fallback if 3D rendering is unavailable. The visual concept lets the user vary azimuth/elevation and inspect the grid-reflector/Yagi/Avenger arrangement against the supplied photograph.

## 3. Controls and modes

| Mode/action | Intended behavior |
|---|---|
| Disconnected | Show saved configuration and last known state with age; hardware actions unavailable; model preview remains usable |
| Manual | Edit explicit azimuth/elevation setpoints; preview locally; send only with Point. Sliders and camera gestures never directly transmit movement |
| Directional jog | The located sketch uses 5° target increments; offer discrete actions after confirming the installed firmware and physical signs, not continuous movement while a button is held |
| Track live rocket | Use validated current rocket position and antenna origin; calculate and send bounded-rate setpoints through the pointer command service |
| Hold tracking | Stop scheduling new tracking targets and clear superseded queued targets; explain the board's actual behavior on the most recent setpoint |
| Zero/reference | The located sketch resets software counters and targets at the current position. Label as Set reference zero after hardware verification; it is not a mechanical homing operation |
| Park/home | Show only when supported and configured; never infer a homing procedure or a mechanically valid park position from a button name |
| Demo/replay | Update the visual model and historical command timeline through a simulated transport; physical serial TX is structurally disabled |

A port write returning successfully advances a command to **Sent**. **Acknowledged** requires a valid board response. **Reached** requires actual measured pose within the configured tolerance, or a verified board-specific completion report. If those capabilities do not exist, show unavailable rather than manufacture them. Motor current, limit switches, calibration state, and pointing error follow the same rule.

Manual controls use the configured mechanical envelope, including allowed negative elevation if the mount supports it. Display geographic azimuth separately from unwrapped motor position when cable routing limits full rotation. Mechanical limits, slew rate, acceleration behavior, and command cadence come from the mount/firmware specification.

Only one motion mode owns the command stream at a time. Switching from tracking to manual cancels unsent tracking requests. Tracking requires an explicit start/resume action after reconnect or loss of a valid target. Reconnecting must not replay stale commands. Do not automatically retry non-idempotent jog or zero operations.

Opening a port may reset some boards through DTR/RTS. Establish line settings on the actual board and invalidate an assumed reference after reset or reconnect. A board's open-loop step count is not encoder feedback, even if a later firmware version transmits it.

If firmware supports an actual stop command and acknowledgments, add a high-priority Stop action with an honest confirmation state. If not, label the available action Hold tracking; it cannot promise immediate physical motor stop. A desktop button is not a replacement for any board-level watchdog or physical stop mechanism. Verify focus loss/release behavior before offering hold-to-jog controls.

## 4. Pointing geometry and tracking

The pointer origin is the antenna pivot location, not automatically the receiver board's antenna or the rocket launch pad. Sources may be a surveyed/manual position or a validated ground-station GNSS fix with explicit offset to the mount. Freeze a selected fixed-site position deliberately, retain its source/time/accuracy, and allow re-surveying. No hard-coded campus coordinates belong in production defaults.

Store origin and rocket position in compatible geodetic/altitude conventions, then calculate line of sight in a local East/North/Up frame. Display azimuth relative to true north and elevation above the local horizon. Apply measured mounting/alignment and antenna boresight offsets before converting to the board's axes/units.

For barometric launch-relative rocket altitude, an absolute target altitude is usable only after establishing the launch altitude and compatible datum. Ground GNSS altitude, launch elevation, and rocket GNSS/barometric altitude must not be mixed without conversion. The legacy adapter's forced zero ground altitude is not retained.

Tracking validation covers source/session identity, fix quality, position age, finite coordinates, correct altitude datum, current mount calibration, travel envelope, cable wrap, and configurable minimum range. Handle nearly overhead targets where azimuth is poorly conditioned; do not create a discontinuous full rotation from a noisy azimuth. Do not interpret a target below the mechanical horizon as a reachable elevation.

Use the newest eligible target and expire obsolete queued setpoints. Choose the command rate and any filtering from measured telemetry cadence and board response. Report filtering/latency if used. Keep the original target, computed geographic angles, constrained motor command, and any rejection/limit reason in the event history.

The located legacy sketch rewrites azimuth moves to the shortest equivalent path. A host-requested long route around a cable limit will therefore not necessarily be followed. Enable only a mechanically verified envelope and reject moves whose full board-selected path cannot be established from a known reference. Unknown winding, slipped steps, or reset require re-establishing that reference. Continuous tracking over a cable-limited mount may require firmware support for limits and unwrapped position; this cannot be solved by a display convention.

When the ground station loses valid rocket position, hold tracking updates with a visible reason and target age. The physical mount's continuation/stop behavior is a firmware capability to establish. Initial tracking uses live measured/onboard-estimated positions only. Simulated trajectories and replay positions remain visual references and must not silently become motor targets. Prediction-assisted tracking would require a separately configured future mode with explicit provenance.

## 5. Legacy pointer protocol: observed versus unknown

The inspected [pointer.py](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/pointer.py) sends 11-byte frames:

| Bytes | Observed encoding |
|---|---|
| 0 | `0xAA` |
| 1 | Command: `0x00` angles, `0x01` up, `0x02` down, `0x03` left, `0x04` right, `0x05` zero |
| 2–5 | Little-endian float azimuth for the angle command |
| 6–9 | Little-endian float elevation for the angle command |
| 10 | Sum of bytes 1–9 modulo 256 |

For directional/zero commands the remaining payload bytes start at zero. Validation located the [board sketch](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Arduino/Zephyrus/antenna_pointer/antenna_pointer/antenna_pointer.ino:101), which corroborates this envelope and checksum. It interprets floats as degrees, negates absolute azimuth internally, ignores changes of 1° or less, uses 5° jog increments, and resets step counters/targets for ZERO. Confirm that this source matches the installed board before relying on those behaviors; its commented angle ranges are not enforced limits.

The Python method reads and prints available bytes. The board sketch prints its elevation target, including after a rejected checksum; that is not an acknowledgment or measured angle. No encoder/status protocol, stop command, or command watchdog was found in the inspected sketch. It continues stepping toward the last target when serial input stops. Implement timestamped raw RX capture first and add structured feedback only against a verified protocol. Do not assume the pointer has its own GPS: the legacy `updateGPS` method updates host-side state from the ground station information.

Preserve a dedicated versioned legacy encoder; new board firmware can provide a separate protocol implementation. Keep raw TX/RX, decoded status, command origin/mode, lifecycle, and timestamps. A saved session records enough information to distinguish requested motion from observed motion.

## 6. Implementation and acceptance

Add `pointer/` services for device transport, protocol encoding/decoding, state machine, target solver, mount configuration, and simulated transport. Add UI components for device-role setup, mount scene, angle instruments, manual/tracking panel, and command timeline. Use the same application themes and renderer capabilities as the flight trajectory view.

The geometry is procedural and lightweight, now informed by the supplied mount photograph. A simplified mesh/CAD asset can refine it later; retain named component IDs and pivots so appearance changes do not alter pointing mathematics. Additional front/rear/elevated views, dimensions, axis locations, and a known zero-angle pose would resolve remaining geometric uncertainty. These are refinement inputs, not a blocker for the current design.

Acceptance criteria:

- Two port roles remain distinct across connects, disconnects, device renumbering, and reconnects; assigning the same device twice is rejected.
- Ground-station acquisition and video continue through pointer errors; manual pointer operation remains possible when telemetry is disconnected.
- Commands match board fixtures, lengths, byte order, units, and checksum; TX and RX buffers are bounded and malformed feedback cannot freeze the UI.
- A model at known poses visibly preserves four fixed timber legs and stakes, the square platform, azimuth-only upper-stage rotation, elevation carrier motion, open curved grid reflector, overhead Yagi, and confirmed lower XR18 placement; the XR18 has an enclosed tapered housing matching the product reference.
- Commanded and measured indicators never merge when feedback is missing or stale; camera orbit and draft sliders cause no physical serial writes.
- Test true-north/east/south/west targets, azimuth wrap, cable limits, horizon, overhead, near-origin positions, origin/altitude offsets, dropped fixes, and reconnects.
- Live-to-replay/demo mode changes make physical motion transmission impossible; replay uses recorded events and a simulated pointer only.
- Simultaneous telemetry, pointer traffic, video, and recording pass the Windows/macOS soak and usability tests.

The reference view and XR18 identification are established, and the legacy sketch provides source evidence for command behavior. Remaining hardware inputs are installed-firmware identity, measured dimensions/pivots, common-versus-independent linkage, actual feedback capabilities, mechanical/cable constraints, reset behavior, and the origin/alignment procedure. These remain tracked in M0 of the main plan.

The accompanying interactive schematic was checked for azimuth/elevation preview updates, explicit demo-command application, separate simulated device disconnects, tracking inhibition when telemetry is unavailable, and manual-command availability independent of telemetry. The narrow layout was checked without horizontal overflow, and the desktop layout was reviewed at 1024 pixels. These checks validate the interface concept only; hardware motion, firmware behavior, and the production Qt renderer remain implementation work.

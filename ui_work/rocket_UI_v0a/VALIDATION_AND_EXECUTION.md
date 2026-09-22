# Plan validation and execution readiness

> Historical planning baseline. Current serial/control behavior follows the original UI as documented in [Legacy feature parity](docs/LEGACY_PARITY.md) and the [Operator guide](docs/OPERATOR_GUIDE.md).
Reviewed 18 September 2026. **Decision: ready to start M0 implementation.** Python/PySide6 remains the recommended desktop stack, with an isolated Java 17 OpenRocket worker. This is an architecture and source review; it does not certify hardware operation, distribution packages, video latency, or flight-model accuracy.

## What the review established

| Area | Evidence and decision | What remains to prove |
|---|---|---|
| Platform and distribution | Qt documents Python 3.10+ and Windows/macOS support; PyInstaller bundles runtimes but requires native builds. Python 3.12 remains a compatible starting candidate. | Lock exact versions after testing the assembled Qt/plot/video/Java bundle on both OSes. |
| Telemetry envelope | Receiver firmware and the old decoder agree on two sync bytes, 128 payload bytes, and 14 receiver bytes at 115200 baud. | Match installed firmware and real captures; freeze payload scaling, checksum coverage, trailer quality and the new rocket protocol. |
| Pointer encoding | Python and located firmware agree on 11 bytes, opcodes 0–5 and additive checksum. Seven capture-only source-encoder checks passed. | Board revision, float representation, physical axis signs, reset behavior and actual motion. |
| Pointer controls | Source specifies 5° target jogs, software-reference ZERO, internal azimuth inversion and a 1° deadband. Printed target elevation is not feedback. | Establish calibrated reference and usable travel/cable envelope; identify any newer firmware capabilities. |
| Pointer route control | Source rewrites azimuth to the shortest path, keeps stepping without new input, and exposes no stop/watchdog/encoder protocol in the inspected sketch. | Qualify a restricted operating envelope or add board support before continuous tracking that needs winding control. Host software cannot force a different path with this protocol. |
| Visual design | User photo and explicit XR18 identification establish component arrangement. Product photographs establish the enclosed XR18 exterior. | Exact dimensions and hidden linkage remain approximate; the Qt renderer still needs implementation. |
| OpenRocket worker | Core tests show a simulation entry point and service initialization. The local fork targets Java 17. | A packaged headless job with a representative team model, complete motor/resources, cancellation, and repeatable outputs. |
| OpenRocket physics | A global roll-inertia override defaults on and is consumed by mass calculation; control/listener defaults are also separate from the rocket file. | Record effective settings and verify nominal mass/inertia first. Three-axis canards and independent tabs require separate model qualification. |
| Weather | Official API documentation supplies pressure-level winds and geopotential heights, supporting the planned adapter. | Real response fixtures, coverage/time handling, conventions, provider usage/attribution, and nominal simulation integration. |
| Video | An isolated FFmpeg adapter is feasible; the actual receiver format has not been supplied. | Single-ingestion display/recording, timestamp preservation, stalled-output isolation and real receiver tests on each OS. |

The review changed the plan in five material ways: incorporated the mount photo; replaced unknown legacy pointer semantics with qualified source evidence; added the shortest-path/cable limitation; made OpenRocket's effective physics settings explicit; and separated immediate demo/package work from hardware-dependent gates.

## Validation performed

- Read the existing telemetry and pointer adapters, receiver and pointer firmware, relevant OpenRocket classes and test initialization, and the installed app's previously audited metadata. References were read as evidence and were not modified.
- Extracted only the legacy pointer's encoding methods into a capture-only sink; no serial module was imported and no device was opened. Checked zero angles, 90°/45°, and all five jog/reference opcodes. The 90°/45° frame was `AA 00 00 00 B4 42 00 00 34 42 6C`. These are source compatibility checks, not board acceptance or proof of the future encoder.
- Verified the revised concept's script syntax and independent demo-device behavior: telemetry loss inhibits tracking, manual operation remains available without telemetry, and pointer disconnection disables demo transmission. Checked desktop/narrow layout and elevated model framing. The preview has no hardware access.
- Rechecked primary documentation for platform support, dependency bundling, weather heights, and FFmpeg build/license considerations. No dependency lock, executable application, worker build, native Windows run, or hardware test was produced in this planning phase.

Local development readiness: this host is Apple Silicon running macOS 26.5. Installed tools include Python 3.12.11 (alongside other versions), Java/Javac 17.0.11, `uv`, and FFmpeg. The default Python is 3.13.13, so use an explicit isolated interpreter/environment. Installed tools are development conveniences, not the release runtime selection. A Windows build/test runner has not been established in this task.

## First implementation sequence

Keep implementation under `rocket_UI_v0/`; keep the legacy monitor and simulation checkout as read-only references. Start with M0a below. M0b can proceed independently when its inputs are available; it does not block the application shell or deterministic data path.

| Order | Task and concrete output | Completion evidence |
|---|---|---|
| M0a.1 | Create `pyproject.toml`, isolated Python environment, package entry point, dependency lock and local build instructions. Select only PySide6 as the Qt binding. | Fresh environment launches a minimal native Qt window; locked dependencies resolve for each intended target. |
| M0a.2 | Create pure domain contracts for mission, source mode/generation, timestamps/quality, telemetry samples, vehicle channel map and pointer state. Add deterministic sample sources and injectable clocks. | Fixtures exercise missing/stale data, configurable canards, four tabs, and distinct requested/sent/measured pointer state without Qt or hardware. |
| M0a.3 | Build the first application shell with separate device-role cards, a rolling plot, basic attitude/trajectory placeholders, and the photo-informed pointer view with a 2D fallback. | Replay/demo never obtains physical serial transport; camera and preview changes cannot transmit. Both device failures remain independent. |
| M0a.4 | Add bundled file-video playback and a Java worker probe using application-relative paths. Define the worker request/result envelope and explicit errors for missing/failed workers. | Video continues while mock telemetry runs; Java starts from the private runtime, reports version and exits; no claim of simulation success from this probe. |
| M0a.5 | Create PyInstaller recipes for a Mac `.app` and Windows folder/ZIP; package sample inputs, runtime resources and notices. Create native build jobs/scripts without publishing or requiring signing secrets for development. | Run each artifact on its corresponding clean OS with internet off and no separate Python/Java/FFmpeg installation; record OS, hashes, startup log and a short acceptance report. |
| M0b.1 | Draft telemetry and pointer interface documents using the located source; add generated fixtures clearly distinguished from captured board bytes. Confirm firmware/capture identity when available. | Parser/encoder fixtures have provenance and expected results; unresolved fields remain explicit. |
| M0b.2 | Specify mount capability profile: axes, true-north alignment, altitude datum, origin, limits, winding/reference state, firmware signs, deadband and reconnect behavior. | Bench procedure covers reference reset, small/large angle changes, jog signs, wrap, disconnect and route limits before enabling physical tracking. |
| M0b.3 | Pin a representative `.ork`, motor, engine inputs and hashes; prototype headless load/run with explicit nominal settings and complete resources. | Compare model mass/inertia and nominal trajectory with the same configured engine; save failure evidence if initialization needs additional services. Keep trajectory import available independently. |
| M0b.4 | Establish the actual receiver format and production OS/architecture matrix. Choose redistributable FFmpeg and Java builds and inventory their contents. | A documented capture test and native dependency/package matrix; no implicit reliance on this developer machine's installations. |

**First reviewable delivery:** a locally runnable native demo plus reproducible packaging recipes and platform-specific artifacts where runners are available. It shows labelled sample telemetry, video, and pointer preview/control state. Include a short completed/pending acceptance report; a missing Windows run leaves that gate pending rather than turning a Mac package into a cross-platform claim.

After M0a, advance to M1's acquisition/record/replay path. Live pointer enablement depends on M0b.1–2, actual receiver certification on M0b.4, and embedded simulation delivery on M0b.3. Keep three-axis model qualification separate from the ability to display measured GNC channels. The main plan's 46–65 engineer-day estimate remains a provisional effort range; no model/firmware extension work has been silently included.

## Contracts to freeze before integration

| Contract | Minimum definition |
|---|---|
| Mission and vehicle profile | Version, units, coordinate/altitude frames, channel IDs/signs, model/configuration identity, site and mount origins. Unknown hardware counts or calibration values cannot default to plausible measured values. |
| Normalized telemetry | Source generation/device session, sample sequence, onboard and host clocks, per-field quality/time, SI values and raw-capture offsets. |
| Pointer command | Command ID, source mode, generation, requested geographic angles, transformed wire angles, expiry, rejection reason and lifecycle. Hardware capabilities determine acknowledgment/reached states. |
| Worker job/result | Contract/job ID, immutable inputs/hashes, engine identity, all effective physics/controller settings, units/frames, branch identity, progress, outputs, warnings and failure/cancellation result. |
| Session | Versioned manifest, raw chunk framing/sequence/receive time, decoded index linkage, pointer TX/RX, video PTS/segments and discontinuities. Define raw-file flush/SQLite commit ordering; rebuild or flag indexes after interruption. |

Mode changes and reconnects invalidate old source generations. A late worker callback, queued tracking target, or old video frame must not repopulate current state. Recording retains full accepted/raw input independently of display decimation; bounded buffers expose explicit faults and loss counts when storage cannot keep up.

## Inputs needed later, without blocking demo work

| Input | Needed before | Owner/source |
|---|---|---|
| New telemetry definition, canard count/signs and measured feedback availability | New-vehicle decoder and final actuator mapping | Avionics/firmware team |
| Installed pointer firmware and physical travel/cable/reference details | Physical manual/tracking qualification | Pointer hardware/firmware owner |
| Video receiver/interface and representative stream | Live video certification | Ground systems owner |
| Production Windows/Mac models, OS versions and runner access | Cross-platform package gate | Production-machine/release owner |
| Representative `.ork`, motor and model qualification targets | Useful integrated simulation | Simulation/GNC owner |
| Distribution/signing identities | Signed production delivery | Release owner |

No additional answer is required to begin the isolated demo foundation. These inputs gate the named integrations, and their absence must remain visible in the acceptance report.

## Source snapshot identity

OpenRocket containing repository HEAD: `1d68549f7318bf619a28efc1024fe56318ae047c`; the two inspected files below had no tracked changes reported. Avionics files are identified by SHA-256 because their supplied root was not a Git checkout.

| Inspected file | SHA-256 |
|---|---|
| `RT_Arduino/Zephyrus/antenna_pointer/antenna_pointer/antenna_pointer.ino` | `635db4c5f08b82ee013880dc6b10f75f8e47e8e1ff62eee846c0ccb0ea8dbc40` |
| `RT_Arduino/Zephyrus/ground_station/ground_station/ground_station.ino` | `c78e6d468e6cf2328416f5513fb31ec2e898de07f4b1ec635afb26c725bb4c8c` |
| `core/.../simulation/listeners/NewControlStepListener.java` | `3a8740dd23311b3252834fa9e9a1ff463f7bb95059859a87c0c01ca3e594309b` |
| `core/.../masscalc/MassCalculation.java` | `e4930387e37dcb885ffb3f5dfd1ec45ea1c4af1c5caa1ed8e678595928a5c21c` |

Exact source locations and line references are in [REFERENCE_AUDIT.md](REFERENCE_AUDIT.md). Snapshot identity does not establish the contents of a deployed board or the installed OpenRocket JAR.

## Primary documentation checked

- [Qt for Python requirements](https://doc.qt.io/qtforpython-6/gettingstarted.html) and [Qt supported platforms](https://doc.qt.io/qt-6/supported-platforms.html): compatibility inputs; select the final OS floor from the complete dependency set.
- [PyInstaller manual](https://pyinstaller.org/en/stable/): bundled-runtime feasibility and native build requirement.
- [FFmpeg license/build guidance](https://ffmpeg.org/legal.html): inventory the exact binary configuration and corresponding distribution materials.
- [Open-Meteo forecast documentation](https://open-meteo.com/en/docs): pressure-level wind and geopotential-height fields; levels are not fixed heights above the launch site.

These are dated review references, not dependency version locks or permission to alter the referenced repositories.

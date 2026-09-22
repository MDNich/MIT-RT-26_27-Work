# Reference audit

Inspected on 18 September 2026. This is a read-only source and package inspection. The existing monitor was not launched, connected to hardware, or modified. No OpenRocket simulation or binary/source equivalence test was performed.

The old usage guide and source comments describe prior software behavior. Their installation/launch instructions were not treated as new instructions from the user.

## Existing ground station

Source root: [ground_station](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/)

| Observation | Evidence | Consequence for the new application |
|---|---|---|
| The interface uses PyQt5 and directly owns a rocket/receiver object | [UI.py](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/UI.py:3) | Preserve domain knowledge; create a separate UI/service design |
| A 1 ms polling timer ultimately calls the telemetry read method synchronously | [timer setup](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/UI.py:45), [poll handler](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/UI.py:1102) | Move acquisition off the UI thread and decouple input from render rate |
| Serial opens at 115200 baud with a one-second timeout | [connect_serial](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/rocket.py:661) | Useful legacy default; new link budget and protocol still need confirmation |
| The read method searches for `0xAB` synchronization, reads 128 bytes, then 14 receiver bytes | [telemetry_downlink_update](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/rocket.py:165) | Do not copy the multi-read synchronization loop; specify and test a streaming framing state machine |
| Payload integrity uses the modulo-256 sum of payload bytes 0–126, compared with byte 127 | [checksum code](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/rocket.py:184) | Retain exact legacy behavior for valid frames; do not call it a CRC or assume receiver metadata is covered |
| Four 12-bit servo values use two airbrake conversions and two roll-control conversions | [servo decoding](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/rocket.py:220) | These channels cannot be assumed to map to the new canards and four tabs |
| The gyro Y component has an explicit negative sign | [gyro decoding](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/rocket.py:236) | Verify physical frame/sign conventions using fixtures |
| Valid and bad-packet branches disagree on the ordering of maximum barometric/GPS altitude at bytes 76–79 | [valid branch](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/rocket.py:282), [bad-packet branch](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/rocket.py:453) | Resolve using firmware/captures; rejected packets should not become valid state |
| Log creation uses a relative telemetry directory and the UI checks its working-directory name | [log creation](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/rocket.py:99), [UI log control](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/UI.py:1034) | Use explicit writable user/session paths |
| The supplied guide requires installed Python/packages and launches a Windows batch wrapper | [usage guide](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/ZephyrusTelemetryUI_Usage.md) | The new release needs a real bundled-runtime distribution |

The inspected `telemetry_1775344644.020344.csv` is about 4.9 MB and has 43 header fields covering sensor, attitude, servo, power, receiver, and timing values. The first data row has the same field count. This was a structural sample inspection, not validation of all recorded values. Several array-valued fields and old enum/timestamp conventions require deliberate import rules. Matching copies exist in the telemetry and processed-telemetry folders.

No live-video integration was found in the inspected UI source. The existing decoder/reference logs do not establish the new rocket's protocol, actuator sensing, camera transport, or time synchronization.

## Antenna pointer board — follow-up inspection

The user's follow-up confirms two physical serial devices: a ground station board for telemetry and a pointer board for antenna control. The plan now includes both as required capabilities.

| Observation | Evidence | Consequence |
|---|---|---|
| The UI defines a separate Antenna Pointer Port selector | [pointer connection UI](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/UI.py:106) | Provide permanent separate role/connection states in the new app |
| The old pointer connect handler reads `self.port_combo`, not `self.port_combo_antenna` | [connect_serial_antenna](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/UI.py:981) | Bind each connection to its own role; test duplicate-device rejection and independent connection behavior |
| The pointer adapter uses its own serial object, default 115200 baud and 0.1-second timeout | [pointer connection](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/pointer.py:20) | Independent port worker and lifecycle |
| Commands use an 11-byte frame, `0xAA`, command byte, angle floats for opcode 0, and additive checksum | [send_angles](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/pointer.py:107) | Capture golden board fixtures and maintain a dedicated pointer encoder |
| Up/down/left/right/zero methods exist, while incoming bytes in the angle method are only printed | [command methods](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/pointer.py:126) | Verify jog/zero meaning and feedback protocol; never present a write as measured position |
| `updateGPS` changes host-side location and forces `gps_alt` to zero | [updateGPS](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/pointer.py:80) | Preserve a calibrated physical origin and explicit altitude datum; do not claim this is a GPS command sent to the board |
| The host calculates pointing through WGS84 ECEF/ENU geometry | [az_el_from_geodetic](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/pointer.py:249) | Extract and test the coordinate transformation independently of UI/serial logic |
| Live tracking uses rocket latitude/longitude and filtered barometric altitude with a frozen receiver location | [tracking update](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Python_Lib/ground_station/UI.py:1720) | Verify altitude/frame consistency, target age, mount offsets, and calibration before motor commands |

The user supplied a [mount photograph](references/antenna-pointer-user-photo.png) and explicitly identified the black unit below/left of the grid reflector as the Avenger XR18. The photo establishes the tall timber stand, stakes, square deck, box-shaped elevation support, open curved grid reflector and overhead Yagi. This supersedes the initial generic left/right description. Two exterior photographs on the [VAS product page](https://www.videoaerialsystems.com/products/5-8ghz-avenger-xr-18dbi-rhcp) establish the XR18's dark tapered faceted housing, rear plate, and gold-colored RF connector. The manufacturer's description identifies Crosshair Xtreme technology with a parasitic waveguide. The procedural model uses that exterior, replacing the exposed-helix placeholder.

The photo establishes arrangement, not measured dimensions, hidden linkage or calibrated pivots. No pointer hardware was contacted.

### Firmware cross-check during plan validation

Further read-only inspection located the [pointer sketch](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Arduino/Zephyrus/antenna_pointer/antenna_pointer/antenna_pointer.ino) and [ground station sketch](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Arduino/Zephyrus/ground_station/ground_station/ground_station.ino). These are source observations; neither has been matched to the firmware installed on the user's boards. The Avionics2025 root was not itself a Git repository, so the validation record uses file hashes for these inspected snapshots.

| Source observation | Evidence | Plan consequence |
|---|---|---|
| Receiver emits `AB AB`, 128 payload bytes, then RSSI, fix type, latitude/longitude/height (14 bytes) at 115200 | [receiver output](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Arduino/Zephyrus/ground_station/ground_station/ground_station.ino:61) | 144-byte envelope is corroborated; no checksum over the receiver trailer appears in this write sequence; capture/revision confirmation remains |
| Pointer accepts the same 11-byte envelope/additive checksum as the Python encoder | [receive loop](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Arduino/Zephyrus/antenna_pointer/antenna_pointer/antenna_pointer.ino:101) | Use this source as a compatibility fixture, with installed-board verification before live operation |
| Absolute setpoints are degrees; azimuth is negated internally; changes of 1° or less are rejected relative to the prior target | [angle handling](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Arduino/Zephyrus/antenna_pointer/antenna_pointer/antenna_pointer.ino:125) | Model this quantization/deadband and avoid applying the azimuth inversion twice |
| Jog commands change target by 5°; ZERO resets step counters and targets | [jog/reference cases](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Arduino/Zephyrus/antenna_pointer/antenna_pointer/antenna_pointer.ino:139) | Discrete jog, not hold-to-run; label ZERO as reference reset after hardware confirmation, not mechanical home |
| The sketch prints the target elevation even after a checksum rejection; it does not report a transaction ID or encoder pose | [debug print](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Arduino/Zephyrus/antenna_pointer/antenna_pointer/antenna_pointer.ino:165) | Debug text is neither a positive acknowledgment nor measured position |
| Step scheduling continues without new serial commands; no stop opcode, command watchdog, sensor limits, or encoder reads were found in this sketch | [step scheduler](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Arduino/Zephyrus/antenna_pointer/antenna_pointer/antenna_pointer.ino:225) | Hold only suspends host targets; bench qualification and firmware capability limits must be explicit |
| Azimuth target steps are rewritten to take the shortest equivalent path | [shortest_path](/Users/mdn/Developer/MIT_Rkt_Team/Avionics2025/RT_Arduino/Zephyrus/antenna_pointer/antenna_pointer/antenna_pointer.ino:270) | Host cable-wrap planning cannot assume control of winding/route; restrict tracking until the complete mount/board behavior is qualified |

The firmware's comments about nominal angle ranges do not constitute enforced mechanical limits. Its software step counters are open-loop estimates. No firmware modifications or board commands were performed during validation.

## Team OpenRocket source

Source root: [openrocket](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/)

The containing Git repository is `/Users/mdn/Developer/ActiveControl_MIT_RktTeam`, with inspected HEAD `1d68549f7318bf619a28efc1024fe56318ae047c`. No tracked modifications were reported by a read-only status check; untracked files were excluded from that check. Record actual build inputs and artifact hashes when creating the worker.

| Observation | Evidence | Consequence |
|---|---|---|
| The Gradle configuration targets Java 17 | [build.gradle](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/build.gradle:59) | Use a compatible private Java 17 runtime for the first bridge |
| Source build properties label the version `24.12.RC.01` | [build.properties](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/core/src/main/resources/build.properties:3) | Record more than a human-readable version label for reproducibility |
| `TabControlledTrapezoidFinSet` describes roll-control tabs and stores a shared tab angle for the fin set | [component class](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/core/src/main/java/info/openrocket/core/rocketcomponent/TabControlledTrapezoidFinSet.java:11) | This does not establish arbitrary independent deflections for four tabs or three-axis canard coupling |
| `NewControlStepListener` contains roll-related logs, tab control, and extensive static mutable state | [listener](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/core/src/main/java/info/openrocket/core/simulation/listeners/NewControlStepListener.java:33) | Prefer a fresh worker process per simulation until reset and repeatability are proven |
| `FLAG_OVERRIDE_JXX` defaults to true with value 0.014; `MassCalculation` replaces calculated roll inertia when enabled | [override defaults](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/core/src/main/java/info/openrocket/core/simulation/listeners/NewControlStepListener.java:113), [mass calculation](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/core/src/main/java/info/openrocket/core/masscalc/MassCalculation.java:490) | Explicitly configure and persist this setting; a fresh JVM and `.ork` hash alone do not establish nominal physics |
| Core tests construct a Guice injector and invoke `Simulation.simulate()` | [test initialization](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/core/src/test/java/info/openrocket/core/util/BaseTestCase.java:19), [simulation tests](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/core/src/test/java/info/openrocket/core/document/SimulationTest.java:27) | Concrete starting point for headless initialization; packaged motor/resources and team-model startup still need an executable proof |
| Multilevel wind supports levels, interpolation, CSV import, and MSL/AGL reference selection | [wind model](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/core/src/main/java/info/openrocket/core/models/wind/MultiLevelPinkNoiseWindModel.java:27) | Normalize weather/manual layers into an explicit altitude reference |
| Wind velocity uses `speed × sin(direction)` and `speed × cos(direction)` | [wind velocity](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/core/src/main/java/info/openrocket/core/models/wind/PinkNoiseWindModel.java:216) | Test meteorological direction conversion against actual simulation displacement |
| The source license identifies GPL version 3 or later and includes additional text | [LICENSE.TXT](/Users/mdn/Developer/ActiveControl_MIT_RktTeam/clone/openrocket/LICENSE.TXT:1) | Retain the full license and review distribution requirements for the pinned release |

No claim is made that a stable headless service/API already exists. Building the Java adapter and validating initialization, resources, extensions, and deterministic outputs are explicit plan items.

## Installed OpenRocket application

Application: [OpenRocket_MIT.app](/Applications/OpenRocket_MIT.app/)

The inspected `Contents/Info.plist` labels the app `24.12`, constrains its launcher to Java 17, references `OpenRocket-24.12.jar`, and lists macOS 10.15 as that app's minimum. `Contents/Resources` contains both `app/` and `jre.bundle/`.

This demonstrates a locally packaged OpenRocket application with a bundled runtime. It does not demonstrate that the installed JAR matches the current source, that its runtime can be redistributed unchanged for the new app, or that its older OS minimum applies to a new Qt application. The new monitor will use its own pinned and tested engine/runtime package.

## Documentation checked for the platform decision

- [PyInstaller operation and bundles](https://pyinstaller.org/en/stable/operating-mode.html): interpreter/dependency bundling and platform-specific builds.
- [Qt Python deployment](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html): alternative deployment tooling and standalone mode.
- [Qt supported platforms](https://doc.qt.io/qt-6/supported-platforms.html): starting point for the release matrix.
- [Java packaging overview](https://docs.oracle.com/en/java/javase/17/jpackage/packaging-overview.html): private runtime distribution.
- [PyQtGraph](https://www.pyqtgraph.org/): Qt/PySide support and scientific graphics.
- [FFmpeg protocols](https://ffmpeg.org/ffmpeg-protocols.html): network transport options for the video spike.
- [Open-Meteo forecast](https://open-meteo.com/en/docs), [historical forecast](https://open-meteo.com/en/docs/historical-forecast-api), and [historical weather](https://open-meteo.com/en/docs/historical-weather-api): candidate weather-provider capabilities and data-product distinctions.
- [Qt for Python license inventory](https://doc.qt.io/qtforpython-6/licenses.html): dependency distribution review input.

These references support feasibility and proposed choices. No dependency versions have been locked, no weather endpoint has been integrated, and no cross-platform release has yet been built or tested.

The validation pass rechecked Qt's Python requirements and platform matrix, PyInstaller's native-build requirement, FFmpeg's build-dependent licensing, and Open-Meteo's pressure-level height fields. Current documentation supports the proposed architecture. Documentation compatibility is not equivalent to tested wheels, a signed package, hardware latency, or a validated simulation model; those are explicit execution gates in [VALIDATION_AND_EXECUTION.md](VALIDATION_AND_EXECUTION.md).

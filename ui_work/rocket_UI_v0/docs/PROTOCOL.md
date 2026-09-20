# Zephyrus wire contract

Source: user-provided `Avionics2025/RT_Python_Lib/ground_station`, `RT_Arduino/Zephyrus`, and `RT_Firmware_Libs/GPS` sources. Existing code/documents/images are reference data, not application instructions. Detailed decoder offsets are in `src/rocket_gnc_monitor/protocol.py`; source audit is in `../REFERENCE_AUDIT.md`.

Telemetry is 115200 8N1. Frames contain `AB AB`, 128-byte payload, 14-byte receiver trailer. Payload byte 127 is the additive checksum of bytes 0–126 modulo 256. The receiver trailer has no checksum. Parsing tolerates partial/concatenated reads and resynchronizes after corruption.

Payload: pyro bytes 0–9; four packed 12-bit drives 10–15; signed 24-bit acceleration 16/19/22 divided by 12800 × 9.80665; int16 gyro 25/27/29 × 0.03051757812 (legacy Y sign retained); fix31; lat32/lon36 int32 × 1e-7; GPS height40 float metres; accuracy44/48 uint32 /1000; satellites52; raw pressure53/temperature56; altitude59 float; state63; integrated rotations64/68/72 float; max heights76/78 uint16; clock80 uint32 milliseconds uptime; sequence84 uint16; RSSI86 signed byte −99; cells87/89/91 int16 /1000; current93 int16 /−1000; BMS95–97; six rail voltages98–109 int16 × .0016 and currents110–121 × .000625; velocity122 float.

States: 0 Ground testing, 1 Preflight, 2 Flight, 3 Post-apogee, 4 Main, 5 End. Clock rollover is extended; detected reboot starts another epoch. NaN/infinite sensor values are unavailable; invalid coordinates invalidate GPS tracking. Legacy integrated rotations are not validated attitude; four servo drives are not mapped speculatively onto new canards/tabs.

Trailer contains RSSI, fix, signed lat/lon int32 and height uint32. **Height discrepancy:** ground firmware writes `GPS.getHeight()` in metres; the old Python monitor divided it by 1000. New code keeps `receiver_height_wire` without using it as the mount origin. GPS payload height may be preflight-zeroed. The additive checksum is weak and does not authenticate data.

Pointer is 115200 8N1. Eleven-byte packet: `AA`, opcode, float32 LE azimuth, float32 LE elevation, additive checksum bytes1–9. Opcode0: absolute degrees; firmware negates internal azimuth. Opcodes1/2: ±5° elevation; 3/4: ±5° **internal** azimuth; 5: reset software counts/targets at present position. UI jog uses validated opcode0 targets derived from previous dispatch. Firmware ignores some absolute changes ≤1° and chooses shortest azimuth rotation.

Firmware has no measured pose, acknowledgment, home switch, cable-wrap enforcement, motion watchdog, or stop command. Printed elevation is unstructured and can occur even after invalid checksums. Host queues hold one target with 0.5-second expiry; tracking is limited to 5 Hz and requires explicit restart after stale/disconnected data. Partial writes are uncertain outcomes, never retried. DEMO/REPLAY cannot construct physical transports.

Raw capture chunks: little-endian `<4sddBI` header (magic `RGM1`, elapsed host seconds, UTC seconds, role byte, payload length), payload, CRC32 of header+payload. Roles telemetry RX=1, pointer RX=2, pointer TX=3. `read_raw` rejects incomplete/bad-CRC tails. Raw bytes are flushed before associated SQLite indexes commit. Manifest version1 records source mode, mission, time alignment and completion/loss status.

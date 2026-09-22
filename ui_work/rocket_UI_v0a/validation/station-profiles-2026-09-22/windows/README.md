# Windows final station-profile validation — 2026-09-22

The final ZIP passed 20 packaged checks from a fresh extraction to a Windows path containing spaces, with only Windows system folders on PATH. The bundled runtime, simulation engine, startup wizard, Base/Away workspaces, Iris routing, serial role separation and video playback were checked.

The affected native Windows regression suite passed 164 tests across 13 modules; one POSIX pseudo-terminal test was skipped on Windows. It passed on macOS. Lint passed. The host is Windows 11 ARM running the x64 application under emulation. Physical USB hardware was not used.

After the initial source suite, the supplied Iris routing diagram was added to the package spec and a native macOS Settings-menu collision was corrected in the common UI. DirectShow discovery also now retains unique alternative identifiers for identically named USB receivers. These final corrections passed the native Windows Settings and camera regressions and lint before this package was rebuilt. Both spec versions, the source/spec diffs, authorized deltas and diagram hash are preserved. Other production Python/Java/build/verifier input hashes stayed unchanged. Results aggregate the source suite and targeted Settings/camera reruns. The native FFmpeg device listing found no attached receivers; duplicate-device routing was verified with representative DirectShow records and independent input reservations. Alternative device names are supported by [FFmpeg DirectShow](https://ffmpeg.org/ffmpeg-devices.html#dshow).

The archive was copied back to macOS and its SHA-256, ZIP CRCs and bundled routing diagram were checked. Earlier interrupted builds are separate intermediate evidence and do not describe this ZIP.

# Windows x64 build — 21 October 2026

Built the current v0a application from repository revision `e6d6ac85`; the latest application source revision is `7e646afa` (Zephyrus gyro integrals are not interpreted as attitude). The only source-tree change for this build corrects a screenshot test for display scaling. The production application is unchanged.

The portable package is `dist/RocketGNCMonitor-v0a-Windows-x64.zip` (214,921,087 bytes). Extract the entire archive and launch `RocketGNCMonitor-v0a/RocketGNCMonitor-v0a.exe`. Python/Qt, FFmpeg, Lucida Grande, OpenRocket-MIT v6.2 and Windows x64 Temurin Java 17 are bundled. The ZIP remains a local build artifact; no GitHub release was created.

## Validation

The full native Windows test run recorded 564 passes, 11 platform skips and three failures. All three failures were screenshot-size assertions at 200% Windows display scaling: 550 logical pixels correctly rendered as 1,100 physical pixels. The corrected tests verify the requested logical size, the device pixel ratio, and Qt's rounded physical screenshot size. The complete affected module then passed all 21 tests in Windows; the three rendering cases also passed locally at scale factors 1 and 1.25. This is a full run followed by a targeted rerun, not a claim that the original full run passed. Four skipped cases require POSIX pseudo-terminals; seven exercise the macOS package builder.

All 20 packaged checks passed from a fresh ZIP extraction in a Windows path containing spaces, with PATH reduced to Windows system directories and Python/Java environment overrides removed. Checks cover startup and settings, launch/away profiles, the Iris/Balius video walls and generated video, all three recorded Zephyrus receiver logs, flight-file round trip, virtual pointer, 3D ignition/recovery events and bundled OpenRocket simulation, including the Zephyrus test-launch model. Screenshots were inspected for the current rocket panel, launch telemetry-board layout, state display and away controls.

Archive CRC and SHA-256 checks passed. All 238 bundled PE binaries are AMD64/x64, including Python, Qt, MGRS, FFmpeg and Java. Engine/bridge/FFmpeg hashes match the bundled build manifest. PyInstaller's recorded application module paths all point to the fresh source snapshot, despite reusing the existing Windows dependency environment.

Testing used the supplied Windows 11 ARM VM with x64 emulation and a native desktop at 200% scaling. Physical x64 Windows hardware and external USB camera/serial boards were not exercised. The executable is unsigned. Build-time warnings about system DLL discovery on the ARM host are retained in the build log; the freshly extracted executable passed the runtime checks.

## Evidence

- [Results](results.json), [packaged report](windows-packaged.json), [archive audit](windows-archive.json), [checksum](SHA256SUMS.txt).
- [Initial full-suite output](windows-tests-initial.txt) and [corrected rendering module](windows-rendering-tests.txt), with corresponding JUnit XML files.
- [Build log](windows-build.txt), [dependencies](windows-dependencies.txt), [source snapshot hashes](source-manifest.json), [frozen module paths](windows-frozen-sources.json).
- [Launch flight display](windows-launch-flight.png), [launch systems display](windows-launch-systems.png), [away display](windows-away.png), [Iris launch video](windows-launch-video-iris.png).

Temporary build/extraction directories were removed after copying the verified ZIP and this evidence. Reusable Windows dependencies and existing Mac packages were preserved.

# v0a cross-platform release — 22 September 2026

The release now includes native Apple Silicon, universal Mac, and Windows x64 ZIP packages. The universal Mac ZIP contains a DMG with one app; its universal launcher selects a complete native Apple Silicon or Intel payload. The Windows ZIP contains the application folder, executable and all private runtimes. Keep the complete package together.

Mac packages require macOS 14 or newer, matching the bundled NumPy runtime. The Intel path was exercised under Rosetta on Apple Silicon; Windows x64 was exercised in the supplied Windows 11 ARM VM under x64 emulation. Physical Intel Mac, Windows x64 and external receiver/PCB tests remain outstanding. Mac signing is ad-hoc and the app is not notarized. Windows is an unsigned development build.

## Corrections included in all builds

- Seeking a recorded demo rebases reception timestamps after history decoding, preserving recorded packet gaps on slower machines.
- Telemetry table updates reuse existing cells. Intel native testing reproduced a PySide table-item destruction crash in the former repeated replacement path; the release includes the cell-lifetime correction.
- Packager validation checks each Mac payload's native library architecture, Java runtime and OpenRocket hashes. The universal launcher preserves arguments and works after relocation.
- Windows tests use platform-independent paths and check the layout after native window creation. The Mac-only packager tests are explicitly scoped to macOS.
- Repeated Windows UI tests complete deferred Qt widget deletion before constructing the next fixture. This is test lifecycle cleanup; the packaged application is unchanged by it.

## Reading the test evidence

The final Mac source suite passed all 142 tests. The later test-fixture cleanup also passed the six affected Mac tests. Both architecture selections of the final universal app passed all 11 packaged checks, and the relocated app passed native LaunchServices and forced Intel startup checks. The Windows package passed the same 11 checks from a fresh ZIP extraction in a path containing spaces, for 33 packaged checks across the three platform/architecture paths.

The initial Windows full-suite log records 134 passes, four skips and two failures: 130 passes were application tests, while the failures were macOS packager symlink tests running without Windows symlink privileges. The complete seven-test macOS packager module is now explicitly skipped on Windows. Three existing POSIX serial tests are also inapplicable there. Targeted Windows reruns cover the changed demo, flight, video and layout behavior; the two new table tests and all six station tests passed after fixture cleanup. These are results across the full run and targeted reruns, not a claim that the initial full run exited successfully.

Build-input hashes identify the checked source. Both Mac payloads have identical Python and Java source. Windows used the same production Python and Java source; its staged spec retained the earlier macOS minimum-version string in the Darwin-only branch, which does not execute during a Windows build. The staged hash is retained in the Windows evidence.

See [results.json](results.json) for test counts, archive checksums and the final packaged reports. The packaged checks exercise both station layouts, locked Live startup, all three Zephyrus logs, both generated video feeds, portable flight files, virtual pointing, 3D events and the bundled OpenRocket engine with a minimal PATH.

Final native screenshots: [Mac flight display](macos-display-1.png), [Mac systems display](macos-display-2.png), [Windows flight display](windows-display-1.png), [Windows systems display](windows-display-2.png). Archive checksums are also available in [SHA256SUMS.txt](SHA256SUMS.txt).

The first Intel check encountered slow initial FFmpeg startup under Rosetta, and a subsequent check exposed the table-item crash. Those findings were investigated before publication; final verification results are separate from those diagnostic attempts. Synthetic video does not validate USB receiver permissions or drivers. LTU-XR management metrics, analog receiver tuning and inter-station audio/video calls remain outside the implemented interface.

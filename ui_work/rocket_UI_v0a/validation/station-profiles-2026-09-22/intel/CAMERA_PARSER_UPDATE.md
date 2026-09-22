# Final camera parser update

The retained `report.json` records the full 20-check Intel package verification immediately before the final camera parser correction. It is not a claim that the full suite was rerun after that correction.

The final package changes Windows DirectShow enumeration to use each USB receiver’s unique alternative device identifier when display names repeat. The macOS enumeration branch is unchanged. Six focused camera tests pass under the Intel runtime.

Module-level comparisons against both previously verified native payloads found exactly one changed module among 662: `rocket_gnc_monitor.media`. Every other Python module and all bootstrap members are byte-identical. Test-only changes do not enter the application archive.

The final Intel native app passes a fresh startup check and deep strict signature verification. Both final universal launcher slices are checked separately, and their Python archives must match the corresponding rebuilt native payloads. Current universal archive hashes and startup evidence are in `../universal/`.

See `camera-parser-delta.json`, `camera-final-package-checks.json`, `camera-final-arm64-module-delta.json`, and `camera-tests.log` for the exact evidence. Prior interrupted attempts remain under `build/` and are not counted as passes.

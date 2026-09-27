# Startup locations and optional saved setup — 26 September 2026

The four-page startup wizard now covers Base/Away 1–4, Telemetry/Video, Balius/Iris and URRG/custom. URRG initializes the pad and selected station positions; new missions use the selected rocket's launch name. Saved mission/flight contents remain authoritative when opened.

Remembering choices is opt-in and initially unchecked. Only `startup-choices.json` supplies remembered defaults; historical automatically saved profiles are ignored. Unchecking the box and finishing, `--no-remember-setup --skip-setup`, or **File → Forget setup on next launch** removes that opt-in. The menu has no shortcut and leaves the active session and other settings intact.

## Checks performed

- Full test suite: **335 passed** (`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`).
- `make lint`, verifier Ruff checks and `git diff --check`: passed.
- Coordinate tests use independently decoded UTM reference values for all five station positions. They cover exact MGRS retention across format changes, elevations, mission/flight round trips and old files without the new preset field.
- Startup tests cover CLI preselection/bypass, both mission names, optional persistence, cancellation, old preferences, and the shared menu action preserving the current mission and unrelated files.
- Native Apple Silicon package rebuilt with the existing bundled OpenRocket/Java runtime. `codesign --verify --deep --strict` passed for its local signature. The [installer checksum](native-installer.sha256) identifies this DMG.
- Packaged checks ran with a minimal system PATH and Qt's offscreen platform. They verified the four wizard pages and unchecked remember option, Iris Away 4 startup, Balius Base's two-window layout, exact startup coordinates/names, LIVE mode and closed physical connections. Reports: [wizard](packaged-wizard.json), [Iris Away 4](packaged-iris-away4.json), [Balius Base](packaged-balius-base.json).
- Visually inspected the [station page](wizard-station.png), [launch-site page](wizard-launch-site.png) and [mission station preset](mission-station-preset.png). Images are Qt renderings, not physical display or device acceptance evidence.

Only the native Mac app and ARM64 DMG were refreshed in this update. Existing universal/Windows artifacts are from the preceding build. No release was created. Temporary PyInstaller/staging output was removed after validation; the runnable app, DMG, dependencies and compact evidence remain.

## Reproduce startup checks

From `rocket_UI_v0a`, use the executable inside the complete app bundle:

```sh
APP=dist/RocketGNCMonitor-v0a.app/Contents/MacOS/RocketGNCMonitor-v0a
QT_QPA_PLATFORM=offscreen "$APP" --setup-smoke --site base --role video --vehicle iris --launch-site urrg --data-dir build/check-setup
QT_QPA_PLATFORM=offscreen "$APP" --startup-smoke --site away4 --role telemetry --vehicle iris --launch-site urrg --skip-setup --data-dir build/check-away4
QT_QPA_PLATFORM=offscreen "$APP" --station-smoke --site base --role telemetry --vehicle balius --launch-site urrg --skip-setup --data-dir build/check-base
```

Presets define horizontal positions only. Launch and antenna elevations remain manual. Physical hardware and station network integration were not exercised by these checks.

# Build and distribution

September 21 revision: Mac only, including smooth antenna animation, 3D flight playback, MGRS/relative antenna positions, virtual pointer rehearsal, corrected native dropdown sizing, Settings, bundled OpenRocket-MIT v6.2, and Digital/Analog USB video. The existing Windows archive is the prior September 18 build and has not been refreshed for these changes.

Use Python 3.12–3.13 (64 bit; x64 Python on Windows), JDK 17+ (`javac` and `jar` on PATH), and GNU Make on the build machine. Build Mac arm64 on Apple Silicon, Mac x86_64 on Intel, and Windows x64 on Windows x64. PyInstaller does not cross-compile. Production users need only the resulting complete package. Lucida Grande is bundled in `resources/fonts/LucidaGrande.ttc` and registered through Qt on Mac and Windows. Preserve the font resource and its provenance notice. The MGRS native library and Open Location Code dependency are bundled for offline location conversion.

```sh
# Mac
make -f Makefile.macos setup PYTHON=python3.12
make -f Makefile.macos all OPENROCKET_JAR="/absolute/path/to/swing-24.12.RC.01-all.jar"
# Windows with GNU Make
make -f Makefile.windows setup
make -f Makefile.windows all OPENROCKET_JAR="C:/OpenRocket/swing-24.12.RC.01-all.jar"
```

The engine can also be fetched at build time from the team's GitHub releases:

```sh
# Embed a local JAR (also prepares the private Java runtime):
make package-macos OPENROCKET_JAR="/absolute/path/to/OpenRocket-MIT-v6.2.jar"
# Resolve the latest published stable release and its OpenRocket-MIT-vX.Y.jar asset:
make package-macos OPENROCKET_DOWNLOAD=latest
# Pin a release for repeatable builds:
make package-macos OPENROCKET_DOWNLOAD=v6.2
# Stage/download the engine and rebuild the bridge without packaging:
make bridge OPENROCKET_DOWNLOAD=latest
```

The same options work with `package`, `package-windows` and both native Makefiles' `all` targets. Select either `OPENROCKET_JAR` or `OPENROCKET_DOWNLOAD`; supplying both is an error. With neither, packaging reuses previously staged vendor files without a network download. A fresh build needs one of the engine options. Settings in a running monitor never trigger downloads.

The downloader queries `MDNich/ActiveControl_MIT_RktTeam/releases/latest` (or `releases/tags/vX.Y`), finds the exact `OpenRocket-MIT-vX.Y.jar` asset, checks its size and published SHA-256 when present, and records release URL, tag, source archive URL, checksum and engine/bridge hashes in `vendor/engine.json`. A missing published digest is explicitly reported and the local hash is still recorded. The current v6.2 release supplies a verified SHA-256. Downloads and bridge compilation happen in a temporary folder; a download, checksum or compilation failure leaves the previously staged bundle intact. Network/rate-limit failures require a retry or a local JAR; there is no silent substitution of another release. Pin a tested release for production builds; a future incompatible release can fail bridge compilation.

Equivalent Windows PowerShell steps without Make:

```powershell
py -3.12 scripts/build.py setup
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/build.py runtime
.venv\Scripts\python.exe scripts/build.py bridge --engine "C:\OpenRocket\swing-24.12.RC.01-all.jar"
.venv\Scripts\python.exe scripts/build.py package --platform Windows
```

Mac outputs: `dist/RocketGNCMonitor.app` and an architecture-labeled DMG. Windows outputs: `dist/RocketGNCMonitor/` and an architecture-labeled ZIP. SHA-256 sidecars accompany distributable archives. Do not copy only the Windows executable; retain its entire folder.

`make setup` uses exact versions in `requirements-build.txt`, exported from `uv.lock`. Developers with uv can run `uv sync --locked`. Internet is needed for initial dependencies/runtime download. Stage dependencies and vendor files in advance for offline builds; never reuse `.venv` or `vendor/java` across OS/CPU architectures.

The bridge requires the **team fork's complete `OpenRocket-MIT-vX.Y.jar` or development `swing-*-all.jar`**, including its motor/resources database. It references fork-specific control fields, so an arbitrary upstream JAR is not interchangeable. `make bridge OPENROCKET_JAR=...` stages it; later `make bridge` can reuse it. Bundled manifests record engine/bridge hashes, Java runtime download/hash, Python versions and FFmpeg configuration. Every simulation job copies model/motor inputs, request, hashes, log and output. Java preferences are private and volatile; desktop OpenRocket settings are not read.

Validation:

```sh
make test
make lint
make smoke
make verify-package
# Headless tests/rendering:
QT_QPA_PLATFORM=offscreen make test
# Packaged smoke without a developer PATH:
PATH=/usr/bin:/bin dist/RocketGNCMonitor.app/Contents/MacOS/RocketGNCMonitor --smoke-test --data-dir build/package-smoke
# Packaged engine test at a synthetic zero-coordinate launch site:
dist/RocketGNCMonitor.app/Contents/MacOS/RocketGNCMonitor --simulation-smoke /path/to/model.ork --data-dir build/package-simulation
```

`make run` starts the default locked LIVE view; `make demo` selects the recorded Zephyrus GS2 launch explicitly. `--startup-smoke` verifies a locked LIVE launch with zero samples and no camera/serial transport. `make verify-package` opens Settings and checks its shortcut/engine, the bundled Lucida Grande family and both coordinate decoders, then runs portable flight/URRG round trips, explicit demo/both-video and engine checks. `--flight-smoke` exercises planning and recorded flight save/load, embedded assets, the exact URRG code and disconnected paused replay in the packaged process.

`scripts/verify_package.py --model /path/to/zephy_testlaunch.ork` additionally runs the supplied model using the packaged motor library and records its resolved motor digest. The N8406 curve is bundled in `resources/motors`; rebuild the bridge with `make bridge` after changing its Java source.

Demo smoke mode uses bundled Zephyrus CSV telemetry plus a synthetic video test pattern, writes `smoke-report.json` and exits. `--demo-station GS1` (or `GS2`/`GS3`) selects a receiver log. The verification script exercises all three recordings from the packaged resources. It never opens serial devices. `make clean` removes only this application's generated `build`/`dist` folders.

Development Mac packages use ad-hoc signing. For release, set `MAC_SIGN_IDENTITY` to the team's Developer ID Application identity before packaging, then notarize/staple the DMG using team credentials. Sign Windows releases with the team's Authenticode certificate. No credentials are included. Camera permission and hardware-specific drivers remain OS/device requirements.

The current Mac package embeds the downloaded OpenRocket-MIT v6.2 release and records its verified release checksum; a reproducible source-to-binary match is not asserted. Rebuild from a recorded source revision and retain source/dependency redistribution materials for a release. macOS metadata targets 13+, but only the recorded host is qualified. Windows 10/11 x64 is intended; the Windows x64 package has been built and tested in the supplied Windows 11 ARM VM under x64 emulation. Physical Windows x64 hardware remains a separate acceptance target.

References: [PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html), [Qt packaging](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html), [Temurin](https://adoptium.net/).

The tested Windows VM used its existing Python 3.13 installation; for setup there, use `make setup PYTHON="py -3.13"`. All subsequent targets use the isolated `.venv`. If building offline, set `PIP_NO_INDEX=1` and `PIP_FIND_LINKS` to a staged wheel folder, including the locked packages plus `hatchling` and `editables` build dependencies. Stage a checksum-verified **Windows x64** JRE in `vendor/java` with its `java-runtime.json`, and make a JDK available on the build process PATH. The VM build and package validation did not require internet access.

The Windows tests use the native Qt Windows platform. Qt's headless `offscreen` platform on Windows needs an explicit font directory and is not equivalent to checking the native window. Mac/Linux CI may use the documented offscreen setting.

`--virtual-pointer-smoke /path/to/trajectory.csv` exercises virtual connection, manual actuation, trajectory playback/seek, and disconnect with no physical serial worker. `make verify-package` runs it against the packaged OpenRocket example output. Its flight-file check also enters an antenna MGRS code, saves/reopens it, switches to a relative offset, and verifies the persisted horizontal vector and altitude.

`--flight-3d-smoke /path/to/trajectory.csv` checks quaternion-backed rocket poses, ignition/burnout boundaries and parachute deployment, saving three renderings. The input must include a burn and a recovery event; packaged verification uses the included small OpenRocket example.

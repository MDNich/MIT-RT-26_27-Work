# Third-party components

Bundled dependency versions/hashes are in `vendor/build-manifest.json`. Python package metadata/licenses are collected at build time. The original OpenRocket JAR is retained intact, including its dependency resources/notices.

| Component | License/source reference |
| --- | --- |
| Qt, PySide6 Essentials, Shiboken | https://www.qt.io/licensing/ ; LGPLv3/GPL/commercial per component, dynamic Qt libraries |
| PyQtGraph | https://github.com/pyqtgraph/pyqtgraph ; MIT |
| NumPy | https://numpy.org/doc/stable/license.html ; BSD-style and included dependency notices |
| pyserial | https://github.com/pyserial/pyserial ; BSD |
| imageio-ffmpeg wrapper | https://github.com/imageio/imageio-ffmpeg ; BSD-2-Clause |
| FFmpeg binary | https://ffmpeg.org/legal.html ; actual build configuration retained in `vendor/ffmpeg-build.txt` |
| Eclipse Temurin Java17 | https://adoptium.net/ ; legal notices retained under `vendor/java/legal` |
| Team OpenRocket fork | GPLv3; `licenses/OpenRocket-GPL.txt`; supplied binary/bridge hashes retained |
| Python | https://docs.python.org/3/license.html ; runtime notices collected at build |
| PyInstaller bootloader | https://pyinstaller.org/en/stable/license.html ; bootloader exception |
| Open-Meteo data | https://open-meteo.com/en/terms ; CC BY 4.0, attribution cached with requests/responses |

FFmpeg binaries come from imageio-ffmpeg; upstream build provenance is maintained at https://github.com/imageio/imageio-binaries . Preserve corresponding source/build details required by the actual configuration for release redistribution. Exact corresponding-source verification for the supplied OpenRocket binary is a release acceptance item. Bridge source is bundled in `vendor/bridge-source`.

The mount photograph was supplied by the user; the procedural model uses no downloaded product artwork. Product reference: https://www.videoaerialsystems.com/products/5-8ghz-avenger-xr-18dbi-rhcp . No signing credentials are included.

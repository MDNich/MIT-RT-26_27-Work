"""Portable build orchestration; only the runtime download needs internet after setup."""

from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import urllib.request
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"


def process_architecture():
    # An x64 Python running under Windows-on-ARM still needs x64 Qt/FFmpeg/Java.
    if platform.system() == "Windows":
        if sysconfig.get_platform() != "win-amd64":
            raise SystemExit(
                "Use 64-bit x86 Python on Windows (also supported through Windows-on-ARM emulation)."
            )
        return "x64"
    return "aarch64" if platform.machine().lower() in {"arm64", "aarch64"} else "x64"


def run(*args, **kwargs):
    print("Running:", " ".join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), cwd=ROOT, check=True, **kwargs)


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def download(url, path):
    request = urllib.request.Request(url, headers={"User-Agent": "RocketGNCMonitor-build/0.1"})
    with urllib.request.urlopen(request, timeout=60) as source, Path(path).open("wb") as target:
        shutil.copyfileobj(source, target)


def setup():
    if sys.version_info < (3, 12):
        raise SystemExit("Build requires Python 3.12 or newer")
    process_architecture()
    env = ROOT / ".venv"
    if not env.exists():
        venv.EnvBuilder(with_pip=True).create(env)
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    # uv-created environments may not contain pip.
    run(python, "-m", "ensurepip", "--upgrade")
    run(python, "-m", "pip", "install", "-r", ROOT / "requirements-build.txt")
    run(python, "-m", "pip", "install", "--no-deps", "-e", ROOT)


def runtime():
    VENDOR.mkdir(exist_ok=True)
    binary = VENDOR / "java" / "bin" / ("java.exe" if os.name == "nt" else "java")
    manifest = VENDOR / "java-runtime.json"
    system = {"Darwin": "mac", "Windows": "windows", "Linux": "linux"}[platform.system()]
    arch = process_architecture()
    if binary.exists() and manifest.exists():
        existing = json.loads(manifest.read_text())
        if (existing.get("os"), existing.get("arch")) != (system, arch):
            raise SystemExit(
                "Staged Java runtime is for another OS/CPU; remove vendor/java and its manifest, then run runtime again."
            )
        run(binary, "-version")
        return
    url = f"https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture={arch}&image_type=jre&os={system}&vendor=eclipse"
    request = urllib.request.Request(
        url, headers={"User-Agent": "RocketGNCMonitor-build/0.1", "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        assets = json.load(response)
    asset = assets[0]
    package = asset["binary"]["package"]
    archive = ROOT / "build" / package["name"]
    archive.parent.mkdir(exist_ok=True)
    download(package["link"], archive)
    if sha(archive) != package["checksum"]:
        raise SystemExit("Java archive checksum mismatch")
    extract = ROOT / "build" / "java-extract"
    if extract.exists():
        shutil.rmtree(extract)
    extract.mkdir()
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                if not (extract / member.filename).resolve().is_relative_to(extract.resolve()):
                    raise SystemExit("Unsafe runtime archive path")
            z.extractall(extract)
    else:
        with tarfile.open(archive) as t:
            t.extractall(extract, filter="data")
    candidates = list(extract.glob("*/Contents/Home")) if system == "mac" else list(extract.iterdir())
    home = next(p for p in candidates if (p / "bin" / ("java.exe" if os.name == "nt" else "java")).exists())
    if (VENDOR / "java").exists():
        shutil.rmtree(VENDOR / "java")
    shutil.copytree(home, VENDOR / "java", symlinks=True)
    write(
        manifest,
        dict(
            version=asset["version"], source=package["link"], sha256=package["checksum"], os=system, arch=arch
        ),
    )
    run(binary, "-version")


def bridge(engine):
    VENDOR.mkdir(exist_ok=True)
    destination = VENDOR / "openrocket.jar"
    if engine:
        source = Path(engine).expanduser().resolve()
        if not source.is_file():
            raise SystemExit(f"Engine JAR not found: {source}")
        if source != destination.resolve():
            shutil.copy2(source, destination)
    if not destination.exists():
        raise SystemExit(
            "Set OPENROCKET_JAR to the team's complete swing-*-all.jar (including engine/resources)."
        )
    build = ROOT / "build" / "bridge"
    build.mkdir(parents=True, exist_ok=True)
    run(
        "javac",
        "--release",
        "17",
        "-encoding",
        "UTF-8",
        "-cp",
        destination,
        "-d",
        build,
        ROOT / "simulation_bridge" / "src" / "RocketBridge.java",
    )
    run("jar", "--create", "--file", VENDOR / "rocket-bridge.jar", "-C", build, ".")
    write(
        VENDOR / "engine.json",
        dict(
            engine_sha256=sha(destination),
            bridge_sha256=sha(VENDOR / "rocket-bridge.jar"),
            source_match="Supplied engine binary; source revision must be verified before production redistribution",
            contract_version=1,
            nominal_only=True,
            inertia_override=False,
        ),
    )
    shutil.copytree(ROOT / "simulation_bridge" / "src", VENDOR / "bridge-source", dirs_exist_ok=True)


def package(target):
    if target and target != platform.system():
        raise SystemExit(f"Build {target} on a native {target} machine; PyInstaller is not a cross-compiler.")
    for required in [VENDOR / "java-runtime.json", VENDOR / "openrocket.jar", VENDOR / "rocket-bridge.jar"]:
        if not required.exists():
            raise SystemExit(f"Missing {required.name}; run make runtime and make bridge first.")
    import imageio_ffmpeg
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(ROOT / "resources" / "icon.svg"))
    iconset = ROOT / "build" / "Rocket.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 64, 128, 256, 512, 1024):
        bitmap = QImage(size, size, QImage.Format.Format_ARGB32)
        bitmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(bitmap)
        renderer.render(painter)
        painter.end()
        if size <= 512:
            bitmap.save(str(iconset / f"icon_{size}x{size}.png"))
        if size >= 32:
            bitmap.save(str(iconset / f"icon_{size // 2}x{size // 2}@2x.png"))
        if size == 256 and platform.system() == "Windows":
            if not bitmap.save(str(ROOT / "build" / "icon.ico"), "ICO"):
                raise SystemExit("Qt could not create the Windows app icon")
    if platform.system() == "Darwin":
        run("iconutil", "-c", "icns", "-o", ROOT / "build" / "icon.icns", iconset)
    import importlib.metadata
    import sysconfig

    licenses = ROOT / "docs" / "licenses"
    for name in (
        "PySide6-Essentials",
        "shiboken6",
        "numpy",
        "pyqtgraph",
        "pyserial",
        "imageio-ffmpeg",
        "pyinstaller",
        "mgrs",
        "openlocationcode",
    ):
        dist = importlib.metadata.distribution(name)
        for file in dist.files or []:
            if (
                any(token in str(file).lower() for token in ("license", "copying", "notice"))
                and dist.locate_file(file).is_file()
            ):
                output = licenses / name / Path(str(file))
                if not output.resolve().is_relative_to(licenses.resolve()):
                    continue
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dist.locate_file(file), output)
    for candidate in (
        Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE.txt",
    ):
        if candidate.exists():
            shutil.copy2(candidate, licenses / "Python-LICENSE.txt")
            break
    metadata = {
        "platform": platform.platform(),
        "architecture": process_architecture(),
        "host_architecture": platform.machine(),
        "python": sys.version,
        "engine": json.loads((VENDOR / "engine.json").read_text()),
        "runtime": json.loads((VENDOR / "java-runtime.json").read_text()),
        "ffmpeg_sha256": sha(imageio_ffmpeg.get_ffmpeg_exe()),
    }
    write(VENDOR / "build-manifest.json", metadata)
    ffinfo = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-version"], capture_output=True, text=True, check=True
    )
    (VENDOR / "ffmpeg-build.txt").write_text(ffinfo.stdout + ffinfo.stderr)
    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        ROOT / "packaging" / "RocketGNCMonitor.spec",
    )
    dist = ROOT / "dist"
    label = process_architecture() if platform.system() == "Windows" else platform.machine()
    base = f"RocketGNCMonitor-{platform.system()}-{label}"
    if platform.system() == "Darwin":
        dmg = dist / (base + ".dmg")
        if dmg.exists():
            dmg.unlink()
        run(
            "hdiutil",
            "create",
            "-volname",
            "Rocket GNC Monitor",
            "-srcfolder",
            dist / "RocketGNCMonitor.app",
            "-ov",
            "-format",
            "UDZO",
            dmg,
        )
        artifact = dmg
    else:
        artifact = Path(
            shutil.make_archive(str(dist / base), "zip", root_dir=dist, base_dir="RocketGNCMonitor")
        )
    (dist / (artifact.name + ".sha256")).write_text(sha(artifact) + "  " + artifact.name + "\n")
    print("Created", artifact)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["help", "setup", "runtime", "bridge", "package", "clean"])
    parser.add_argument("--engine", default=os.environ.get("OPENROCKET_JAR", ""))
    parser.add_argument("--platform", default="")
    args = parser.parse_args()
    if args.command == "help":
        print("make setup | run | test | lint | runtime | bridge OPENROCKET_JAR=/path/to/swing-all.jar")
        print("make package-macos (on Mac) | package-windows (on Windows) | smoke")
    elif args.command == "setup":
        setup()
    elif args.command == "runtime":
        runtime()
    elif args.command == "bridge":
        bridge(args.engine)
    elif args.command == "package":
        package(args.platform)
    elif args.command == "clean":
        for name in ("build", "dist"):
            path = ROOT / name
            if path.exists():
                shutil.rmtree(path)


if __name__ == "__main__":
    main()

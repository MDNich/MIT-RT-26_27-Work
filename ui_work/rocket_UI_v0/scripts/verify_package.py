"""Exercise the packaged application and its private runtimes with a minimal PATH."""

from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "package-verification")
    args = parser.parse_args()
    package = (
        args.package
        or ROOT / "dist" / ("RocketGNCMonitor.app" if sys.platform == "darwin" else "RocketGNCMonitor")
    ).resolve()
    executable = (
        package / "Contents" / "MacOS" / "RocketGNCMonitor"
        if sys.platform == "darwin"
        else package / ("RocketGNCMonitor.exe" if os.name == "nt" else "RocketGNCMonitor")
    )
    contents = package / "Contents" / "Resources" if sys.platform == "darwin" else package / "_internal"
    model = contents / "resources" / "examples" / "simple.ork"
    if not executable.is_file() or not model.is_file():
        raise SystemExit("Package executable/example model missing")
    environment = dict(os.environ)
    environment["PATH"] = (
        (str(Path(os.environ["SystemRoot"]) / "System32") + ";" + os.environ["SystemRoot"])
        if os.name == "nt"
        else "/usr/bin:/bin"
    )
    for key in ("PYTHONPATH", "PYTHONHOME", "JAVA_HOME", "IMAGEIO_FFMPEG_EXE"):
        environment.pop(key, None)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    commands = [
        (
            "startup",
            [
                "--startup-smoke",
                "--data-dir",
                str(output / "startup"),
                "--screenshot",
                str(output / "startup.png"),
            ],
        ),
        (
            "demo",
            ["--smoke-test", "--data-dir", str(output / "demo"), "--screenshot", str(output / "window.png")],
        ),
        ("simulation", ["--simulation-smoke", str(model), "--data-dir", str(output / "simulation")]),
    ]
    for name, arguments in commands:
        run = subprocess.run(
            [str(executable), *arguments], cwd=package, env=environment, capture_output=True, timeout=150
        )
        (output / (name + ".log")).write_bytes(run.stdout + run.stderr)
        if run.returncode:
            raise SystemExit(f"{name} failed ({run.returncode}); see {output}")
    demo = json.loads((output / "demo" / "smoke-report.json").read_text())
    startup = json.loads((output / "startup" / "smoke-report.json").read_text())
    if (
        startup["mode"] != "LIVE"
        or not startup["controls_locked"]
        or startup["hardware_open"]
        or startup["samples"]
        or startup["video_frames"]
    ):
        raise SystemExit("Packaged application did not start in locked Live mode")
    simulation = json.loads((output / "simulation" / "simulation-smoke-report.json").read_text())
    if demo["hardware_open"] or demo["samples"] <= 20 or demo["video_frames"] <= 0:
        raise SystemExit("Packaged demo did not receive telemetry/video or opened hardware")
    if simulation["rows"] < 2 or not math.isfinite(simulation["apogee_m"]) or simulation["apogee_m"] <= 0:
        raise SystemExit("Packaged simulation did not produce a usable example trajectory")
    if simulation["manifest"]["name"] != "OpenRocket nominal · A simple model rocket":
        raise SystemExit("Packaged simulation returned a damaged model label; check UTF-8 encoding")
    (output / "report.json").write_text(
        json.dumps(
            dict(package=str(package), minimal_path=True, startup=startup, demo=demo, simulation=simulation),
            indent=2,
        )
    )
    print(f"Packaged Live startup, demo/video and private OpenRocket engine passed: {output}")


if __name__ == "__main__":
    main()

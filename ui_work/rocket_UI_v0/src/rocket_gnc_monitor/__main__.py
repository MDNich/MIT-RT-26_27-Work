from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="Rocket GNC Monitor")
    parser.add_argument("--data-dir", type=Path)
    startup = parser.add_mutually_exclusive_group()
    startup.add_argument("--demo", action="store_true", help="Play the recorded Zephyrus test flight")
    parser.add_argument("--demo-station", choices=["GS1", "GS2", "GS3"], default="GS2")
    startup.add_argument("--smoke-test", action="store_true", help="Exercise recorded demo playback and exit")
    startup.add_argument("--startup-smoke", action="store_true", help="Verify locked Live startup and exit")
    parser.add_argument(
        "--screenshot", type=Path, help="Save a native window rendering during the smoke test"
    )
    parser.add_argument(
        "--simulation-smoke",
        type=Path,
        help="Test the private engine using a model and synthetic launch coordinates",
    )
    args = parser.parse_args()
    if args.simulation_smoke:
        from .domain import Mission, write_json
        from .trajectory import SimulationJob

        directory = args.data_dir or Path.cwd() / "simulation-smoke"
        trajectory = SimulationJob(
            Mission(site_configured=True, model=str(args.simulation_smoke)), directory
        ).run()
        write_json(
            directory / "simulation-smoke-report.json",
            dict(
                rows=len(trajectory.points),
                apogee_m=float(trajectory.points[:, 3].max()),
                manifest=trajectory.manifest,
            ),
        )
        return 0
    from PySide6.QtCore import QStandardPaths, QTimer
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontInfo, QFontDatabase
    from .fonts import configure_fonts
    from .ui import MainWindow

    app = QApplication(sys.argv[:1])
    font_id = configure_fonts(app)
    app.setApplicationName("RocketGNCMonitor")
    app.setOrganizationName("MITRocketTeam")
    data = args.data_dir or Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    )
    window = MainWindow(data)
    if args.demo or args.smoke_test:
        window.controller.demo_station = args.demo_station
        window.controller.switch_mode("DEMO")
        window.pages.setCurrentIndex(1)
    window.show()
    if args.smoke_test or args.startup_smoke:

        def complete():
            from .location import decode_mgrs, decode_plus_code

            c = window.controller
            mgrs_location = decode_mgrs("15TWG0000049776")
            plus_location = decode_plus_code("8FVC9G8F+6X")
            report = dict(
                samples=len(c.history),
                mode=c.mode,
                video_frames=c.video.received_frames if c.video else 0,
                video_error=c.video.error if c.video else "",
                hardware_open=any(c.workers.values()),
                demo_recording=dict(station=c.demo.station, **c.demo.metadata) if c.demo else None,
                demo_progress_samples=c.demo_replayed_rows,
                latest_demo_row=c.latest.details.get("demo_row") if c.latest else None,
                latest_recorded_utc=c.latest.utc if c.latest else None,
                controls_locked=not window.record_button.isEnabled() and not window.point_button.isEnabled(),
                font_family=QFontInfo(app.font()).family(),
                bundled_font_families=QFontDatabase.applicationFontFamilies(font_id),
                location_checks={
                    "mgrs": [mgrs_location.latitude, mgrs_location.longitude],
                    "pluscode": [plus_location.latitude, plus_location.longitude],
                },
            )
            data.mkdir(parents=True, exist_ok=True)
            (data / "smoke-report.json").write_text(json.dumps(report, indent=2))
            if args.screenshot:
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                window.grab().save(str(args.screenshot))
            window.close()
            valid = (
                report["mode"] == "LIVE"
                and report["samples"] == 0
                and report["video_frames"] == 0
                and report["controls_locked"]
                if args.startup_smoke
                else report["mode"] == "DEMO"
                and report["demo_progress_samples"] > 20
                and report["video_frames"] > 0
            )
            app.exit(0 if valid and not report["hardware_open"] else 1)

        QTimer.singleShot(1000 if args.startup_smoke else 4500, complete)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

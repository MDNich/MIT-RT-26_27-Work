from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="Rocket GNC Monitor")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--station", choices=["base", "away"], help="Workspace: base uses two displays; away uses one")
    startup = parser.add_mutually_exclusive_group()
    startup.add_argument("--demo", action="store_true", help="Play the recorded Zephyrus test flight")
    parser.add_argument("--demo-station", choices=["GS1", "GS2", "GS3"], default="GS2")
    startup.add_argument("--smoke-test", action="store_true", help="Exercise recorded demo playback and exit")
    startup.add_argument("--startup-smoke", action="store_true", help="Verify locked Live startup and exit")
    startup.add_argument("--station-smoke", action="store_true", help="Verify station workspace layout and exit")
    startup.add_argument(
        "--virtual-pointer-smoke",
        type=Path,
        help="Rehearse a georeferenced trajectory with the virtual pointer and exit",
    )
    startup.add_argument(
        "--flight-3d-smoke", type=Path, help="Verify 3D attitude, ignition and recovery playback"
    )
    startup.add_argument(
        "--flight-smoke", action="store_true", help="Verify portable flight files and the URRG preset"
    )
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
    from .station_workspace import StationWindow as MainWindow

    app = QApplication(sys.argv[:1])
    font_id = configure_fonts(app)
    app.setApplicationName("RocketGNCMonitor-v0a")
    app.setOrganizationName("MITRocketTeam")
    data = args.data_dir or Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    )
    window = MainWindow(data, station=args.station, auto_place=not args.station_smoke)
    if args.demo or args.smoke_test:
        window.controller.demo_station = args.demo_station
        window.controller.switch_mode("DEMO")
        window.pages.setCurrentIndex(1)
    window.show()
    if args.station_smoke:
        def station_check():
            try:
                window.resize(1920, 1020)
                window.companion.resize(1920, 1020)
                app.processEvents()
                window.grab().save(str(data / "display-1.png"))
                if window.station_mode == "base":
                    window.companion.grab().save(str(data / "display-2.png"))
                report = dict(
                    station_mode=window.station_mode, source_mode=window.controller.mode,
                    shared_controller=window.controller is window.companion.controller,
                    window_count=sum(w.isVisible() for w in (window, window.companion)),
                    visible_cards=[key for key, card in window.cards.items() if card.isVisible()],
                    hardware_open=any(window.controller.workers.values()),
                    shortcuts_shared=all(a in window.companion.actions() for a in window.legacy_actions.values()),
                )
                (data / "station-smoke-report.json").write_text(json.dumps(report, indent=2))
                window.close()
            except Exception:
                import traceback
                traceback.print_exc()
                window.close()
                app.exit(1)
        QTimer.singleShot(700, station_check)
        return app.exec()
    if args.flight_3d_smoke:
        from .trajectory import Trajectory

        c = window.controller
        c.timer.stop()
        c.reference = Trajectory.load(args.flight_3d_smoke)
        assert c.reference.motion is not None
        window.open_flight_3d()
        dialog = window.flight_3d_dialog
        dialog.timer.stop()
        burns = dialog.scene.burns
        deployments = dialog.scene.deployments
        assert burns and deployments
        snapshots = [
            ("ignition", (burns[0][0] + burns[0][1]) / 2),
            ("burnout", burns[0][1]),
            ("parachute", deployments[0]["time"] + 1),
        ]
        frames = {}
        for name, stamp in snapshots:
            dialog.playback.seek(stamp)
            dialog.last_labels = 0
            dialog.tick()
            app.processEvents()
            frame = dialog.view.frame
            frames[name] = dict(
                time=frame.time,
                powered=frame.powered,
                recovery=frame.recovery,
                attitude=frame.attitude,
                state=frame.state,
            )
            dialog.grab().save(str(data / (name + ".png")))
        assert frames["ignition"]["powered"] and not frames["burnout"]["powered"]
        assert frames["parachute"]["recovery"]
        assert all("Simulation attitude" in frame["attitude"] for frame in frames.values())
        report = dict(
            frames=frames, motion_rows=len(c.reference.motion), hardware_open=any(c.workers.values())
        )
        (data / "flight-3d-smoke-report.json").write_text(json.dumps(report, indent=2))
        window.close()
        return 0
    if args.virtual_pointer_smoke:
        from .trajectory import Trajectory
        from .virtual_pointer import VIRTUAL_POINTER_DEVICE

        c = window.controller
        c.timer.stop()
        c.reference = Trajectory.load(args.virtual_pointer_smoke)
        lat, lon, altitude = c.reference.manifest["origin"]
        c.mission.pointer_latitude = lat - 0.001
        c.mission.pointer_longitude = lon - 0.001
        c.mission.pointer_altitude = altitude
        c.mission.pointer_site_configured = True
        c.connect("pointer", VIRTUAL_POINTER_DEVICE)
        c.tick()
        c.manual_point(90, 30)
        c.tick()
        c.virtual_pointer.advance(2)
        assert c.virtual_pointer.pose == (90, 30)
        c.start_virtual_trajectory()
        c.advance_virtual_flight(1, 1e20)
        assert c.virtual_flight.time > c.virtual_flight.start
        c.seek_virtual_trajectory((c.virtual_flight.start + c.virtual_flight.end) / 2)
        c.tick()
        c.virtual_pointer.advance(4)
        window.pages.setCurrentIndex(2)
        window.last_ui = 0
        window.refresh()
        app.processEvents()
        report = dict(
            mode=c.mode,
            virtual_connected=bool(c.virtual_pointer),
            physical_ports_open=any(
                worker and worker is not c.virtual_pointer for worker in c.workers.values()
            ),
            samples=len(c.history),
            telemetry_locked=not window.record_button.isEnabled(),
            pose=c.virtual_pointer.pose,
            target=c.virtual_pointer.target,
            trajectory_time=c.virtual_flight.time,
            range_m=c.virtual_flight.distance,
            paused=not c.virtual_flight.playing,
            model_label=c.reference.manifest.get("name"),
        )
        (data / "virtual-pointer-smoke-report.json").write_text(json.dumps(report, indent=2))
        if args.screenshot:
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(args.screenshot))
        c.disconnect("pointer")
        assert c.virtual_pointer is None and c.virtual_flight is None
        window.close()
        return (
            0
            if report["virtual_connected"] and not report["physical_ports_open"] and report["samples"] == 0
            else 1
        )
    if args.flight_smoke:
        from .flight import save_flight, load_flight
        from .demo import DemoFlight
        from .trajectory import Trajectory
        from .ui import MissionDialog
        from .domain import to_enu

        c = window.controller
        dialog = MissionDialog(c.mission)
        dialog.location.preset.setCurrentIndex(dialog.location.preset.findData("URRG"))
        dialog.pointer_location.format.setCurrentIndex(dialog.pointer_location.format.findData("mgrs"))
        dialog.pointer_location.mgrs.setText("18T UN 20615 30290")
        dialog.fields["pointer_site_configured"].setChecked(True)
        dialog.accept()
        assert dialog.mission.pointer_location_code == "18TUN2061530290"
        assert dialog.mission.pointer_latitude == dialog.mission.latitude
        pointer_mgrs = dialog.mission.pointer_location_code
        dialog.mission.save(data / "antenna-mgrs.json")
        from .domain import Mission

        dialog = MissionDialog(Mission.load(data / "antenna-mgrs.json"))
        dialog.pointer_location.format.setCurrentIndex(dialog.pointer_location.format.findData("relative"))
        dialog.pointer_location.heading.setValue(90)
        dialog.pointer_location.distance.setValue(500)
        dialog.pointer_location.height_difference.setValue(5)
        dialog.accept()
        mission = dialog.mission
        mission.model = str(window.resource_root / "resources" / "examples" / "simple.ork")
        reference = Trajectory(
            [[0, 0, 0, 0], [1, 0, 0, 10]],
            dict(schema_version=1, frame="ENU", units="m,s", origin=[mission.latitude, mission.longitude, 0]),
        )
        archive = data / "planning.rktflight"
        save_flight(archive, mission, reference)
        planning = load_flight(archive, data / "opened")
        c.apply_flight(planning)
        assert c.mode == "LIVE" and c.reader is None and c.reference is not None
        assert c.mission.launch_location_code == "18TUN2061530290"
        assert c.mission.pointer_location_format == "relative"
        antenna_enu = to_enu(
            c.mission.latitude,
            c.mission.longitude,
            c.mission.altitude,
            (c.mission.pointer_latitude, c.mission.pointer_longitude, c.mission.pointer_altitude),
        )
        assert abs(antenna_enu[0] - 500) < 1e-4 and abs(antenna_enu[1]) < 1e-4
        assert c.mission.pointer_altitude == c.mission.altitude + 5
        assert Path(c.mission.model).is_file()
        demo = DemoFlight("GS2")
        archive = data / "zephyrus.rktflight"
        save_flight(
            archive,
            mission,
            reference,
            demo=demo,
            position=demo.launch_time + 2,
            mode="DEMO",
            flight_zero=demo.flight_zero,
            time_aligned=True,
            scope="Complete Zephyrus GS2 dataset",
        )
        loaded = load_flight(archive, data / "opened")
        c.apply_flight(loaded)
        window.task_done("flight_loaded", loaded)
        window.last_ui = 0
        window.refresh()
        report = dict(
            mode=c.mode,
            samples=c.reader.count,
            paused=not c.replay_playing,
            hardware_open=any(c.workers.values()),
            site=c.mission.launch_site_name,
            code=c.mission.launch_location_code,
            pointer_location=dict(
                mgrs=pointer_mgrs,
                format=c.mission.pointer_location_format,
                heading=c.mission.pointer_launch_heading,
                distance=c.mission.pointer_launch_distance,
                height_difference=c.mission.pointer_height_difference,
                launch_enu=antenna_enu,
            ),
            model_exists=Path(c.mission.model).is_file(),
            reference_rows=len(c.reference.points),
            latest_row=c.latest.details["demo_row"],
        )
        (data / "flight-smoke-report.json").write_text(json.dumps(report, indent=2))
        if args.screenshot:
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(args.screenshot))
        window.close()
        return (
            0
            if report["samples"] == len(demo.rows) and report["paused"] and not report["hardware_open"]
            else 1
        )
    if args.smoke_test or args.startup_smoke:

        def complete():
            from .location import decode_mgrs, decode_plus_code

            c = window.controller
            mgrs_location = decode_mgrs("15TWG0000049776")
            plus_location = decode_plus_code("8FVC9G8F+6X")
            window.open_settings()
            settings_check = dict(
                visible=window.settings_dialog.isVisible(),
                shortcut=window.settings_action.shortcut().toString(),
                bundled_engine=c.settings.engine_path.is_file(),
                engine_status=window.settings_dialog.engine_status.text(),
            )
            window.settings_dialog.reject()
            report = dict(
                settings=settings_check,
                samples=len(c.history),
                mode=c.mode,
                video_frames=c.video.received_frames if c.video else 0,
                video_error=c.video.error if c.video else "",
                video_streams={
                    stream: dict(
                        frames=state.worker.received_frames if state.worker else 0,
                        error=state.worker.error if state.worker else state.error,
                    )
                    for stream, state in c.video_streams.items()
                },
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
                and all(v["frames"] == 0 for v in report["video_streams"].values())
                and report["controls_locked"]
                if args.startup_smoke
                else report["mode"] == "DEMO"
                and report["demo_progress_samples"] > 20
                and all(v["frames"] > 0 and not v["error"] for v in report["video_streams"].values())
            )
            app.exit(0 if valid and not report["hardware_open"] else 1)

        QTimer.singleShot(1000 if args.startup_smoke else 4500, complete)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

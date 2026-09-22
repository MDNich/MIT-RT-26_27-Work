"""Two-display base station and one-display away station over one instrument owner.

The v0 widgets remain the single source of control callbacks and telemetry state.
Only their presentation changes: no second Controller, duplicate serial worker,
hidden operational tab, or separate command implementation is introduced here.
"""

import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QTableWidget,
    QSizePolicy,
    QHeaderView,
    QFileDialog,
    QTableWidgetItem,
)

from .ui import MainWindow as InstrumentWindow, button, label
from .widgets import ComboBox
from .flight_view import Flight3DDialog
from .media import camera_devices
from .domain import finite


COMPACT_STYLE = """
QWidget { font-size: 11px; }
QLabel#heading { font-size: 20px; }
QLabel#section { font-size: 12px; font-weight: 600; }
QLabel#eyebrow { font-size: 10px; letter-spacing: 1px; }
QLabel#metric { font-size: 24px; }
QPushButton { padding: 4px 7px; border-radius: 4px; }
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox { padding: 3px 5px; }
QHeaderView::section { padding: 3px 2px; font-size: 10px; }
QTableWidget::item { padding: 1px 3px; }
QFrame#card { border-radius: 7px; }
QCheckBox { spacing: 4px; }
QCheckBox::indicator { width: 12px; height: 12px; }
"""


def row(*widgets, stretch=False):
    layout = QHBoxLayout()
    layout.setSpacing(5)
    for widget in widgets:
        layout.addWidget(widget)
        widget.show()
    if stretch:
        layout.addStretch()
    return layout


class EmbeddedFlightView(Flight3DDialog):
    """Keep the mandatory flight panel visible when Escape bubbles from a child."""

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)


class StationDisplay(QMainWindow):
    """A companion display shares ownership and cannot silently lose its panels."""

    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Window)
        self.owner = owner
        self.controller = owner.controller
        self.setWindowTitle("Rocket GNC Monitor v0a · 2 / Systems & video")
        self.setWindowIcon(owner.windowIcon())
        self.resize(1920, 1020)
        self.setMinimumSize(1280, 800)

    def closeEvent(self, event):
        if self.owner.closing or self.owner.station_mode == "away":
            event.accept()
        else:
            event.ignore()
            self.statusBar().showMessage(
                "Base station uses both displays. Choose Away station for one window.", 8000
            )


class StationWindow(InstrumentWindow):
    def __init__(self, data_dir, station=None, auto_place=True):
        self.workspace_ready = False
        self.closing = False
        self.auto_place = auto_place
        self.station_mode = "base"
        super().__init__(data_dir)
        self.setWindowTitle("Rocket GNC Monitor v0a · 1 / Flight & antenna")
        self.setMinimumSize(1280, 800)
        self.resize(1920, 1020)
        # Keep old containers alive: their child widgets and signals are reused.
        self.instrument_storage = self.takeCentralWidget()
        self.instrument_storage.setParent(self)
        self.instrument_storage.hide()
        self.cards = {}
        self.companion = StationDisplay(self)
        self.companion.setStyleSheet(self.styleSheet() + COMPACT_STYLE)
        self.station_path = Path(data_dir) / "station-layout.json"
        if station is None:
            try:
                station = json.loads(self.station_path.read_text()).get("station", "base")
            except (OSError, ValueError, AttributeError):
                station = "base"
        self.build_workspace()
        # One QAction can be installed on two windows without duplicate bindings.
        for action in (*self.legacy_actions.values(), *self.flight_actions.values()):
            self.companion.addAction(action)
        self.companion.addAction(self.settings_action)
        self.workspace_ready = True
        self.set_daylight(self.controller.settings.daylight, persist=False)
        self.refresh_actuators()
        self.set_station_mode(station if station in ("base", "away") else "base", persist=False)
        self.last_ui = 0
        self.refresh()
        QApplication.instance().screenAdded.connect(self.screens_changed)
        QApplication.instance().screenRemoved.connect(self.screens_changed)

    def card(self, key, title):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setProperty("stationCard", key)
        panel.setMinimumSize(0, 0)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(9, 7, 9, 7)
        layout.setSpacing(5)
        layout.addWidget(label(title, "section"))
        self.cards[key] = panel
        return layout

    def attach(self, layout, widget, stretch=0):
        widget.setMinimumSize(0, 0)
        widget.setMaximumSize(16777215, 16777215)
        widget.setSizePolicy(
            QSizePolicy.Policy.Ignored if stretch else QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Ignored if stretch else QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(widget, stretch)
        widget.show()

    def build_workspace(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 9, 12, 5)
        outer.setSpacing(6)
        self.station_selector = ComboBox()
        self.station_selector.addItem("Base station · two displays", "base")
        self.station_selector.addItem("Away station · one display", "away")
        self.station_selector.setAccessibleName("Station workspace")
        self.station_selector.currentIndexChanged.connect(
            lambda: self.set_station_mode(self.station_selector.currentData())
        )
        heading = row(label("ROCKET / v0a", "heading"), self.station_selector, self.mission_label)
        heading.addStretch()
        heading.addWidget(label("DATA SOURCE", "eyebrow"))
        for widget in (self.mode, self.poll_button, self.record_button):
            heading.addWidget(widget)
            widget.show()
        outer.addLayout(heading)
        self.usb_strip = QWidget()
        usb = QHBoxLayout(self.usb_strip)
        usb.setContentsMargins(0, 0, 0, 0)
        for role, title in (("telemetry", "Telemetry PCB / USB"), ("pointer", "Antenna PCB / USB")):
            combo, connect, status = self.port_widgets[role]
            usb.addWidget(label(title, "section"))
            for w in (combo, self.refresh_buttons[role], connect, self.disconnect_buttons[role], status):
                usb.addWidget(w, 1 if w is combo else 0)
                w.show()
        outer.addWidget(self.usb_strip)
        self.attach(outer, self.demo_bar)
        self.health = QLabel()
        self.health.setObjectName("eyebrow")
        outer.addWidget(self.health)
        metric_strip = QHBoxLayout()
        for key, title in (
            ("altitude", "ALTITUDE · m"),
            ("velocity", "VELOCITY · m/s"),
            ("flight", "FLIGHT TIME · s"),
            ("battery", "BATTERY · V"),
            ("rssi", "RADIO · dBm"),
            ("age", "SAMPLE AGE · s"),
        ):
            box = QFrame()
            box.setObjectName("card")
            line = QHBoxLayout(box)
            line.setContentsMargins(10, 4, 10, 4)
            line.addWidget(label(title, "muted"))
            line.addStretch()
            line.addWidget(self.metrics[key])
            self.metrics[key].show()
            metric_strip.addWidget(box, 1)
        outer.addLayout(metric_strip)
        self.flight_board = QWidget()
        self.flight_grid = QGridLayout(self.flight_board)
        self.flight_grid.setContentsMargins(0, 0, 0, 0)
        self.flight_grid.setSpacing(7)
        outer.addWidget(self.flight_board, 1)
        self.attach(outer, self.banner)

        root2 = QWidget()
        self.companion.setCentralWidget(root2)
        secondary = QVBoxLayout(root2)
        secondary.setContentsMargins(12, 9, 12, 5)
        secondary.setSpacing(6)
        title = row(label("SYSTEMS / VIDEO", "heading"))
        self.secondary_health = label("LIVE · Ground station disconnected", "eyebrow")
        title.addWidget(self.secondary_health, 1)
        title.addWidget(button("Arrange displays", self.arrange_displays))
        title.addWidget(button("Settings…", self.open_settings))
        secondary.addLayout(title)
        self.systems_board = QWidget()
        self.systems_grid = QGridLayout(self.systems_board)
        self.systems_grid.setContentsMargins(0, 0, 0, 0)
        self.systems_grid.setSpacing(7)
        secondary.addWidget(self.systems_board, 1)
        self.secondary_banner = label("", "muted")
        secondary.addWidget(self.secondary_banner)

        self.build_flight_cards()
        self.build_pointer_cards()
        self.build_system_cards()
        self.build_operations_cards()
        self.rocket_panel.setParent(self.companion)
        self.rocket_panel.hide()
        for parent in (self, self.companion):
            for table in parent.findChildren(QTableWidget):
                table.setMinimumSize(0, 0)
                table.verticalHeader().setMinimumSectionSize(17)
                table.verticalHeader().setDefaultSectionSize(20)
                table.horizontalHeader().setMinimumSectionSize(28)
                table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        view_menu = next(a.menu() for a in self.menuBar().actions() if a.text() == "View")
        view_menu.addAction("Arrange station displays", self.arrange_displays)
        view_menu.addAction("Base station · two displays", lambda: self.set_station_mode("base"))
        view_menu.addAction("Away station · one display", lambda: self.set_station_mode("away"))
        # Same menu actions remain usable from the second display on macOS.
        for menu_action in self.menuBar().actions():
            if menu_action.menu():
                self.companion.menuBar().addMenu(menu_action.menu())

    def build_flight_cards(self):
        self.flight_3d_dialog = EmbeddedFlightView(self.controller, self)
        scene = self.flight_3d_dialog
        scene.setWindowFlags(Qt.WindowType.Widget)
        scene.setMinimumSize(0, 0)
        scene.view.setMinimumSize(0, 0)
        # Rearrange its controls into two rows without changing the playback engine.
        old = scene.layout()

        def clear(layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().hide()
                if item.layout():
                    clear(item.layout())

        clear(old)
        old.setContentsMargins(0, 0, 0, 0)
        old.setSpacing(3)
        old.addLayout(
            row(
                scene.camera,
                scene.follow,
                scene.projection,
                scene.velocity,
                scene.size,
                button("Fit", scene.view.fit),
            )
        )
        scene.follow.setText("Follow")
        scene.projection.setText("Ground")
        scene.view.setMinimumHeight(130)
        old.addWidget(scene.view, 1)
        old.addLayout(row(scene.play_button, scene.rewind, scene.speed, scene.link, scene.events))
        scene.link.setText("Monitor time")
        old.addWidget(scene.slider)
        old.addWidget(scene.status)
        for w in (scene.view, scene.slider, scene.status):
            w.show()
        scene.title.hide()
        scene.status.setFixedHeight(28)
        layout = self.card("flight3d", "FLIGHT / 3D simulation & events")
        self.attach(layout, scene, 1)
        layout = self.card("trajectory", "GROUND TRACK / reference & actual")
        self.attach(layout, self.trajectory_plot, 1)
        layout.addLayout(row(self.view, button("Import…", self.load_reference)))
        self.attach(layout, self.reference_label)
        self.reference_label.setFixedHeight(26)
        layout = self.card("altitude", "VERTICAL PROFILE / m")
        self.attach(layout, self.altitude_plot, 1)
        layout = self.card("attitude", "ROCKET ATTITUDE")
        self.attach(layout, self.attitude, 1)
        self.attach(layout, self.attitude_label)
        self.attitude_label.setFixedHeight(18)
        for key, title, graph in (
            ("gnc_rates", "ANGULAR RATES / °/s", self.rate_plot),
            ("gnc_angles", "INTEGRATED ROTATION / °", self.angle_plot),
        ):
            self.attach(self.card(key, title), graph, 1)
        layout = self.card("actuators", "GNC / canards, tabs & legacy channels")
        self.attach(layout, self.actuators, 1)
        note = label("Zephyrus: four drive values; new actuator feedback unavailable.", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)

    def build_pointer_cards(self):
        layout = self.card("antenna", "ANTENNA / physical assembly")
        layout.addLayout(
            row(
                *(
                    button(name, lambda checked=False, n=name: self.mount_camera(n))
                    for name in ("Perspective", "Front", "Side", "Top")
                )
            )
        )
        self.attach(layout, self.mount, 1)
        self.mount.display_center = (0, 2.25, 0)
        self.mount.display_padding = 20
        self.mount.show_hints = False
        self.mount.setToolTip("Drag to orbit · Scroll to zoom · Double-click to reset")
        self.attach(layout, self.pointer_sent)
        layout = self.card("pointing", "POINTING / control & rehearsal")
        layout.addLayout(row(self.pointer_pose, self.virtual_connect))
        layout.addLayout(
            row(label("Azimuth °"), self.azimuth, label("Elevation °"), self.elevation, self.point_button)
        )
        jogs = [w for w in self.pointer_controls if isinstance(w, QPushButton) and w is not self.point_button]
        layout.addLayout(row(*jogs, self.zero_button))
        layout.addLayout(row(self.track_button, self.hold_button))
        self.attach(layout, self.pointer_status)
        self.attach(layout, self.ground_gps_title)
        self.attach(layout, self.ground_gps)
        layout.addLayout(row(self.freeze_gps, button("Antenna location…", self.edit_pointer_mission)))
        # Preserve visibility switching driven by refresh_virtual_pointer().
        virtual = self.virtual_panel.layout()
        while virtual.count():
            item = virtual.takeAt(0)
            if item.widget():
                item.widget().hide()
        virtual.setContentsMargins(0, 2, 0, 0)
        virtual.setSpacing(3)
        virtual.addLayout(row(self.virtual_follow, self.virtual_reset, self.virtual_speed))
        for w in (self.virtual_slider, self.virtual_clock, self.virtual_pose, self.virtual_location):
            virtual.addWidget(w)
            w.show()
        self.attach(layout, self.virtual_panel)
        layout.addStretch()

    def build_system_cards(self):
        for stream, title in (
            ("digital", "DIGITAL / USB video receiver"),
            ("analog", "ANALOG / USB video receiver"),
        ):
            v = self.video_widgets[stream]
            layout = self.card(stream, title)
            self.attach(layout, v["image"], 1)
            self.attach(layout, v["status"])
            v["status"].setFixedHeight(18)
            video_row = row(
                v["camera"],
                button("Find", lambda: self.controller.submit("cameras", camera_devices)),
                v["start"],
                v["stop"],
                v["file"],
            )
            video_row.setStretch(0, 1)
            layout.addLayout(video_row)
        rp = self.rocket_panel
        for key, title, widget in (
            ("telemetry", "ROCKET / full telemetry", rp.telemetry),
            ("gps", "ROCKET / GPS", rp.gps),
            ("servos", "LEGACY SERVOS", rp.servos),
            ("cells", "BATTERY CELLS / V", rp.cells),
            ("power", "POWER RAILS / requested & measured", rp.power),
            ("bms", "BMS / enabled & triggered protections", rp.protections),
        ):
            self.attach(self.card(key, title), widget, 1)
        layout = self.card("commands", "ROCKET COMMANDS / Zephyrus")
        grid = QGridLayout()
        grid.setSpacing(4)
        for i, command in enumerate(
            ("advance_state", "zero_pitchYawRoll", "zero_alt", "zero_velo", "zero_servos", "pd_activate")
        ):
            grid.addWidget(rp.buttons[command], i // 3, i % 3)
        layout.addLayout(grid)
        for title, name in (
            ("Roll °", "set_roll_control_servo_angle"),
            ("Airbrakes °", "set_airbrakes_angle"),
        ):
            layout.addLayout(row(label(title), rp.servo_inputs[name], rp.buttons[name]))
        layout.addLayout(row(label("VTX"), *rp.vtx_buttons))
        layout = self.card("recovery", "RECOVERY / continuity, arm & fire")
        self.attach(layout, rp.pyros, 1)
        layout.addLayout(row(rp.buttons["arm_pyros"], rp.buttons["fire_pyros"]))
        emergency = QGridLayout()
        emergency.setSpacing(4)
        for i, command in enumerate(
            ("EMERG_DEPLOY_PISTON", "EMERG_DEPLOY_BP_WELLS", "EMERG_DEPLOY_TD", "EMERG_DEPLOY_ALL")
        ):
            emergency.addWidget(rp.buttons[command], i // 2, i % 2)
        layout.addLayout(emergency)

    def build_operations_cards(self):
        layout = self.card("mission", "MISSION / launch, wind & OpenRocket")
        layout.addLayout(
            row(
                button("Configure…", self.edit_mission),
                button("Open mission…", self.load_mission),
                button("Save mission…", self.save_mission),
            )
        )
        self.attach(layout, self.mission_summary)
        self.mission_summary.setMaximumHeight(32)
        self.attach(layout, self.wind_table, 1)
        layout.addLayout(
            row(
                button("+ Layer", lambda: self.add_wind_row(1000, 0, 0)),
                button("− Layer", self.remove_wind_row),
                button("Apply", lambda: self.guard(self.apply_wind)),
                button("Import", self.import_wind),
                button("Export", self.export_wind),
            )
        )
        self.attach(layout, self.wind_status)
        self.wind_status.setMaximumHeight(28)
        self.weather_time.setToolTip("Weather valid time, UTC ISO 8601")
        self.weather_msl.setToolTip("Launch elevation above mean sea level, metres")
        layout.addLayout(
            row(
                label("UTC"),
                self.weather_time,
                label("MSL m"),
                self.weather_msl,
                button("Weather", self.fetch_weather),
            )
        )
        layout.addLayout(
            row(self.model_path, button("Model…", self.choose_model), button("Motors…", self.choose_motors))
        )
        self.attach(layout, self.motor_status)
        self.motor_status.setMaximumHeight(18)
        layout.addLayout(
            row(
                button("Run simulation", lambda: self.guard(self.start_simulation), True),
                button(
                    "Cancel",
                    lambda: self.controller.simulation.cancel() if self.controller.simulation else None,
                ),
            )
        )
        self.attach(layout, self.sim_status)
        self.sim_status.setMaximumHeight(32)
        layout = self.card("sessions", "FLIGHT FILE / recording & replay")
        layout.addLayout(
            row(
                button("Open flight…", self.open_flight),
                button("Save flight…", self.save_flight),
                button("Session…", self.open_session),
                button("CSV import", self.import_legacy_csv),
                button("CSV export", self.export_session),
            )
        )
        self.attach(layout, self.flight_file_status)
        self.flight_file_status.setMaximumHeight(27)
        self.attach(layout, self.session_status)
        self.session_status.setMaximumHeight(27)
        self.attach(layout, self.replay_slider)
        layout.addLayout(
            row(self.play, self.step_button, self.speed, self.replay_clock, self.align_time_button)
        )
        self.align_time_button.setText("Set t = 0")
        self.play.setText("Play / pause")
        layout = self.card("diagnostics", "DIAGNOSTICS / alerts, decoded sample & events")
        layout.addLayout(row(self.alert_status, button("Acknowledge", self.controller.acknowledge_alerts)))
        self.attach(layout, self.link_stats)
        panes = QHBoxLayout()
        for w in (self.details, self.log_view, self.timeline):
            w.setMinimumSize(0, 0)
            w.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
            panes.addWidget(w, 1)
            w.show()
        layout.addLayout(panes, 1)
        from .station_panel import StationNetworkPanel

        self.network_panel = StationNetworkPanel(self.controller)
        self.attach(self.card("network", "GROUND NETWORK / APRS & local stations"), self.network_panel, 1)

    def place(self, grid, key, r, c, rs=1, cs=1):
        widget = self.cards[key]
        grid.addWidget(widget, r, c, rs, cs)
        widget.show()

    def set_station_mode(self, value, persist=True):
        if not self.workspace_ready:
            return
        if value not in ("base", "away"):
            raise ValueError("Station mode must be base or away")
        self.station_mode = value
        self.mount.zoom = 1.4 if value == "base" else 1.0
        for grid in (self.flight_grid, self.systems_grid):
            while grid.count():
                item = grid.takeAt(0)
                if item.widget():
                    item.widget().hide()
            for i in range(16):
                grid.setRowStretch(i, 0)
                grid.setColumnStretch(i, 0)
        for panel in self.cards.values():
            panel.hide()
        if value == "base":
            self.setWindowTitle("Rocket GNC Monitor v0a · 1 / Flight & antenna")
            for args in (
                ("flight3d", 0, 0, 2, 2),
                ("trajectory", 2, 0, 1, 1),
                ("altitude", 2, 1, 1, 1),
                ("antenna", 0, 2, 1, 1),
                ("pointing", 1, 2, 2, 1),
                ("attitude", 0, 3, 1, 1),
                ("gnc_rates", 1, 3, 1, 1),
                ("gnc_angles", 2, 3, 1, 1),
                ("actuators", 3, 0, 1, 4),
            ):
                self.place(self.flight_grid, *args)
            for i, weight in enumerate((32, 24, 24, 20)):
                self.flight_grid.setRowStretch(i, weight)
            for i, weight in enumerate((20, 20, 30, 30)):
                self.flight_grid.setColumnStretch(i, weight)
            # Four columns keep every former tab and nested tab in view.
            for args in (
                ("digital", 0, 0, 1, 1),
                ("analog", 0, 1, 1, 1),
                ("telemetry", 1, 0, 1, 1),
                ("gps", 1, 1, 1, 1),
                ("servos", 2, 0, 1, 1),
                ("cells", 2, 1, 1, 1),
                ("diagnostics", 3, 0, 1, 2),
                ("commands", 0, 2, 1, 1),
                ("power", 1, 2, 1, 1),
                ("bms", 2, 2, 1, 1),
                ("recovery", 3, 2, 1, 1),
                ("mission", 0, 3, 2, 1),
                ("sessions", 2, 3, 1, 1),
                ("network", 3, 3, 1, 1),
            ):
                self.place(self.systems_grid, *args)
            for i, weight in enumerate((23, 31, 15, 31)):
                self.systems_grid.setRowStretch(i, weight)
            for i, weight in enumerate((22, 22, 25, 31)):
                self.systems_grid.setColumnStretch(i, weight)
            if self.isVisible():
                self.companion.show()
        else:
            self.setWindowTitle("Rocket GNC Monitor v0a · Away station")
            self.companion.hide()
            for args in (
                ("antenna", 0, 0, 2, 1),
                ("pointing", 2, 0, 2, 1),
                ("altitude", 0, 1, 2, 1),
                ("attitude", 2, 1, 2, 1),
                ("telemetry", 0, 2, 2, 1),
                ("gps", 2, 2, 2, 1),
            ):
                self.place(self.flight_grid, *args)
            for i in range(4):
                self.flight_grid.setRowStretch(i, 1)
            for i, weight in enumerate((42, 30, 28)):
                self.flight_grid.setColumnStretch(i, weight)
        self.station_selector.blockSignals(True)
        self.station_selector.setCurrentIndex(self.station_selector.findData(value))
        self.station_selector.blockSignals(False)
        if persist:
            try:
                self.station_path.parent.mkdir(parents=True, exist_ok=True)
                self.station_path.write_text(json.dumps({"station": value}, indent=2) + "\n")
            except OSError as exc:
                self.statusBar().showMessage(f"Workspace preference not saved: {exc}", 8000)
        self.rescale_videos()

    def open_flight_3d(self):
        if not self.workspace_ready:
            return
        if self.station_mode != "base":
            self.set_station_mode("base")
        self.flight_3d_dialog.load_reference()
        self.flight_3d_dialog.tick()
        self.activateWindow()
        self.cards["flight3d"].setFocus()

    def start_camera(self, stream="digital"):
        # The video computer has USB receivers, but no telemetry PCB (board diagram).
        if self.controller.mode == "REPLAY":
            raise ValueError("Close replay before selecting a USB receiver")
        source = self.video_widgets[stream]["camera"].currentData()
        if source is None or source == "":
            raise ValueError("Find and select a USB camera first")
        self.controller.start_video("camera", source, stream=stream)
        self.update_camera_choices()

    def video_file(self, stream="digital"):
        if self.controller.mode == "REPLAY":
            return
        path, _ = QFileDialog.getOpenFileName(
            self, f"{stream.title()} video source", "", "Video (*.mp4 *.mkv *.mov *.avi *.ts);;All files (*)"
        )
        if path:
            self.controller.start_video("file", path, stream=stream)

    def refresh_actuators(self):
        if not self.workspace_ready:
            return super().refresh_actuators()
        c = self.controller
        channels = {f"Canard {i + 1}": {} for i in range(c.mission.canard_count)}
        channels.update({f"Tab {i + 1}": {} for i in range(4)})
        if c.latest:
            channels.update(c.latest.actuators)
        self.actuators.setColumnCount(len(channels))
        self.actuators.setRowCount(4)
        self.actuators.setHorizontalHeaderLabels(list(channels))
        self.actuators.setVerticalHeaderLabels(["Requested °", "Measured °", "Drive µs", "Status"])
        self.actuators.verticalHeader().show()
        for column, values in enumerate(channels.values()):
            items = [
                f"{values[k]:.2f}" if finite(values.get(k)) else "—" for k in ("demand", "measured", "drive")
            ]
            items.append("Drive only" if "drive" in values else "Unavailable")
            for r, value in enumerate(items):
                self.actuators.setItem(r, column, QTableWidgetItem(value))

    def arrange_displays(self):
        screens = QApplication.screens()
        primary = self.screen() or screens[0]
        second = next((s for s in screens if s is not primary), primary)
        for window, screen in ((self, primary), (self.companion, second)):
            rect = screen.availableGeometry()
            window.setGeometry(rect.adjusted(4, 4, -4, -4))
        if second is primary and self.station_mode == "base":
            self.companion.move(primary.availableGeometry().topLeft() + QPoint(28, 28))
            self.statusBar().showMessage(
                "One display detected. Connect a second display, then choose Arrange displays.", 12000
            )

    def screens_changed(self, *_):
        if self.workspace_ready and self.auto_place:
            QTimer.singleShot(100, self.arrange_displays)

    def showEvent(self, event):
        super().showEvent(event)
        if self.workspace_ready:
            if self.station_mode == "base":
                self.companion.show()
            if self.auto_place:
                QTimer.singleShot(0, self.arrange_displays)

    def rescale_videos(self):
        for stream, pixmap in self.last_pixmaps.items():
            if pixmap:
                view = self.video_widgets[stream]["image"]
                view.setPixmap(
                    pixmap.scaled(
                        view.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

    def refresh(self):
        previous = self.last_ui
        super().refresh()
        if not self.workspace_ready or self.last_ui == previous:
            return
        c = self.controller
        self.usb_strip.setVisible(c.mode != "DEMO")
        status = "   /   ".join(
            self.connection_tiles[k].text().replace("● ", "") for k in ("ground", "rocket", "pointer")
        )
        self.health.setText("USB TELEMETRY · RADIO LINK · ANTENNA   /   " + status)
        self.secondary_health.setText(c.mode + " · " + self.connection_tiles["rocket"].text())
        self.secondary_banner.setText(self.banner.text())
        self.network_panel.refresh()
        for stream, widgets in self.video_widgets.items():
            state = c.video_streams[stream]
            available = c.mode != "REPLAY" and not (state.config or state.reserved_cameras)
            widgets["start"].setEnabled(available and bool(widgets["camera"].currentData()))
            widgets["file"].setEnabled(c.mode != "REPLAY")
            widgets["start"].setToolTip("Start this USB video receiver independently of telemetry USB")
            widgets["file"].setToolTip("Open a local video source")
        if c.mode != "REPLAY" and any(s.worker and s.worker.last_frame for s in c.video_streams.values()):
            self.record_button.setEnabled(True)
            self.legacy_actions["log"].setEnabled(True)
        for table in (
            self.actuators,
            self.rocket_panel.telemetry,
            self.rocket_panel.gps,
            self.rocket_panel.servos,
            self.rocket_panel.cells,
            self.rocket_panel.power,
            self.rocket_panel.protections,
            self.rocket_panel.pyros,
            self.wind_table,
        ):
            for index in range(table.rowCount()):
                table.setRowHeight(index, 19)
        for table, names in (
            (
                self.rocket_panel.telemetry,
                (
                    "State",
                    "RSSI (dBm)",
                    "RX RSSI (dBm)",
                    "Baro altitude (m)",
                    "Max baro altitude (m)",
                    "Roll (°)",
                    "Integrated velocity (m/s)",
                    "Angle from vertical (°)",
                    "Temperature (°C)",
                    "Last reception (ms)",
                    "Packet number",
                ),
            ),
            (
                self.rocket_panel.gps,
                (
                    "GPS fix",
                    "Latitude",
                    "Longitude",
                    "Altitude (m)",
                    "Max altitude (m)",
                    "Horizontal precision (m)",
                    "Vertical precision (m)",
                    "Satellites",
                ),
            ),
        ):
            table.setRowCount(len(names))
            for r, name in enumerate(names):
                table.setItem(r, 0, QTableWidgetItem(name))
                if not c.latest:
                    table.setItem(r, 1, QTableWidgetItem("—"))
                table.setRowHeight(r, 19)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(0, round(table.viewport().width() * 0.58))
        self.rocket_panel.power.setItem(7, 0, QTableWidgetItem("Temp °C"))
        for col in (0, 1):
            self.rocket_panel.pyros.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        # Fixed-size instrument readouts must not hide their final channel/field.
        # Logs, imported wind layers and raw JSON remain bounded scrolling panes.
        for table in (
            self.actuators,
            self.rocket_panel.telemetry,
            self.rocket_panel.gps,
            self.rocket_panel.servos,
            self.rocket_panel.cells,
            self.rocket_panel.power,
            self.rocket_panel.protections,
            self.rocket_panel.pyros,
        ):
            table.setMinimumHeight(
                sum(table.rowHeight(r) for r in range(table.rowCount()))
                + table.horizontalHeader().height()
                + 4
            )

    def set_daylight(self, enabled, *, persist=True):
        super().set_daylight(enabled, persist=persist)
        if self.workspace_ready:
            style = self.styleSheet() + COMPACT_STYLE
            self.setStyleSheet(style)
            self.companion.setStyleSheet(style)

    def closeEvent(self, event):
        self.closing = True
        if self.workspace_ready:
            self.network_panel.shutdown()
            self.companion.close()
        super().closeEvent(event)

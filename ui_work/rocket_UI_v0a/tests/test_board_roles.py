"""Dedicated base uplink, receive-only away stations and legacy wire compatibility."""

import gc
import os
import queue
import select
import threading
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from rocket_gnc_monitor.controller import Controller
from rocket_gnc_monitor.devices import SerialWorker
from rocket_gnc_monitor.domain import demo_sample
from rocket_gnc_monitor.protocol import pointer_packet
from rocket_gnc_monitor.recording import SessionReader, SessionRecorder, read_raw
from rocket_gnc_monitor.ui import MainWindow
from rocket_gnc_monitor.zephyrus import rocket_packet
from test_protocol import frame


class Board:
    def __init__(self, role, device, generation, emit, raw):
        self.role, self.device, self.generation = role, device, generation
        self.emit, self.raw = emit, raw
        self.stop_event = threading.Event()
        self.commands = queue.Queue()
        self.sent = []
        self.polling = False
        self.emit(generation, role, "connected", device)

    def send(self, payload, command_id):
        self.sent.append((payload, command_id))

    def set_polling(self, enabled):
        self.polling = enabled

    def stop(self):
        self.stop_event.set()


@pytest.fixture
def boards(monkeypatch):
    monkeypatch.setattr("rocket_gnc_monitor.controller.SerialWorker", Board)


def test_base_commands_use_only_uplink_and_downlink_controls_remain_independent(qtbot, tmp_path, boards):
    c = Controller(tmp_path, board_layout="base")
    try:
        assert tuple(c.serial_labels) == ("telemetry", "uplink", "pointer")
        c.connect("telemetry", "downlink")
        c.tick()
        downlink = c.workers["telemetry"]
        assert c.ground_connected and not c.command_connected and not c.can_command
        with pytest.raises(ValueError, match="Uplink board is disconnected"):
            c.send_rocket("zero_alt")
        c.set_polling(True)
        c.connect("uplink", "uplink")
        c.tick()
        uplink = c.workers["uplink"]
        assert c.command_connected and c.can_command and downlink.polling
        assert not uplink.polling
        c.send_rocket("zero_alt")
        assert not downlink.sent and uplink.sent[0][0] == rocket_packet("zero_alt")
        command_id = uplink.sent[0][1]
        c.enqueue(downlink.generation, "telemetry", "sent", command_id)
        c.tick()
        assert command_id in c.rocket_commands
        c.disconnect("telemetry")
        assert not c.ground_connected and not c.polling and c.can_command
        assert command_id in c.rocket_commands
        c.enqueue(uplink.generation, "uplink", "sent", command_id)
        c.tick()
        assert command_id not in c.rocket_commands
        c.send_rocket("zero_velo")
        assert uplink.sent[-1][0] == rocket_packet("zero_velo")
        c.disconnect("uplink")
        assert not c.can_command and not c.rocket_commands
    finally:
        c.shutdown()


@pytest.mark.parametrize("mode", ["LIVE", "DEMO", "REPLAY"])
def test_away_station_never_transmits_rocket_commands(qtbot, tmp_path, boards, mode):
    c = Controller(tmp_path, board_layout="away")
    try:
        c.connect("telemetry", "downlink")
        c.tick()
        downlink = c.workers["telemetry"]
        c.mode = mode
        assert not c.can_command and not c.command_connected
        with pytest.raises(ValueError, match="Away stations"):
            c.send_rocket("zero_alt")
        assert not downlink.sent and not c.rocket_commands
        assert "uplink" not in c.serial_labels
        c.mode = "LIVE"
        with pytest.raises(ValueError, match="Unknown serial role"):
            c.connect("uplink", "other")
    finally:
        c.shutdown()


def test_iris_live_commands_wait_for_target_protocol_but_base_demo_can_simulate(qtbot, tmp_path, boards):
    c = Controller(tmp_path, board_layout="base", vehicle="iris")
    events = []
    c.event.connect(events.append)
    try:
        c.connect("uplink", "uplink")
        c.tick()
        uplink = c.workers["uplink"]
        assert c.command_connected and not c.can_command
        with pytest.raises(ValueError, match="target protocol pending"):
            c.send_rocket("zero_alt")
        assert not uplink.sent
        c.mode = "DEMO"
        assert c.can_command
        c.send_rocket("zero_alt")
        assert events[-1] == "Rocket command simulated" and not uplink.sent
    finally:
        c.shutdown()


def test_uplink_messages_cannot_inject_telemetry_recordings_or_pointer_updates(qtbot, tmp_path, boards):
    c = Controller(tmp_path / "app", board_layout="base")
    try:
        for role in c.serial_labels:
            c.connect(role, role)
        c.tick()
        c.set_polling(True)
        path = c.start_recording(tmp_path / "sessions")
        uplink = c.workers["uplink"]
        c.pointer_sent = (45, 20)
        c.pointer_pending = ("pointer-command", (50, 25))
        c.dispatched_commands["pointer-command"] = (50, 25)
        c.command_names["pointer-command"] = "manual"
        before = dict(c.stats)
        for kind, data in (("sample", demo_sample(0, 1)), ("stats", dict(accepted=999)),
                           ("sent", "pointer-command"), ("expired", "pointer-command"), ("rx", "aa bb")):
            c.enqueue(uplink.generation, "uplink", kind, data)
        c.tick()
        assert c.latest is None and not c.history and c.stats == before
        assert c.pointer_sent == (45, 20) and c.pointer_pending[0] == "pointer-command"
        assert "pointer-command" in c.dispatched_commands
        c.disconnect("uplink")
        assert c.pointer_pending[0] == "pointer-command"
        c.stop_recording()
        c.recording_close_future.result(timeout=5)
        reader = SessionReader(path)
        try:
            assert reader.count == 0 and reader.manifest["complete"]
            assert any(event["name"] == "Uplink RX: aa bb" for _, event in reader.events(60))
        finally:
            reader.close()
    finally:
        c.shutdown()


def test_legacy_default_still_transmits_on_telemetry_board(qtbot, tmp_path, boards):
    c = Controller(tmp_path)
    try:
        assert tuple(c.serial_labels) == ("telemetry", "pointer")
        c.connect("telemetry", "legacy")
        c.tick()
        assert c.can_command and c.command_connected and c.command_role == "telemetry"
        c.send_rocket("zero_alt")
        assert c.workers["telemetry"].sent[0][0] == rocket_packet("zero_alt")
    finally:
        c.shutdown()


def test_three_serial_dropdowns_exclude_connected_aliases_and_uplink_unlocks_commands(qtbot, tmp_path, boards, monkeypatch):
    devices = [dict(device=port) for port in ("/dev/cu.A", "/dev/tty.A", "/dev/cu.B", "/dev/cu.C")]
    monkeypatch.setattr("rocket_gnc_monitor.ui.ports", lambda: devices)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    window = MainWindow(tmp_path, board_layout="base")
    qtbot.addWidget(window)
    c = window.controller

    def choices(role):
        combo = window.port_widgets[role][0]
        return {combo.itemData(index) for index in range(combo.count())}

    try:
        assert tuple(window.port_widgets) == ("telemetry", "uplink", "pointer")
        c.connect("telemetry", "/dev/cu.A")
        c.tick()
        window.refresh_connections(time.monotonic())
        window.update_port_choices(force=True)
        assert not {"/dev/cu.A", "/dev/tty.A"} & choices("uplink")
        assert not {"/dev/cu.A", "/dev/tty.A"} & choices("pointer")
        assert not window.rocket_panel.buttons["zero_alt"].isEnabled()
        c.connect("uplink", "/dev/cu.B")
        c.tick()
        window.refresh_connections(time.monotonic())
        window.update_port_choices(force=True)
        assert window.rocket_panel.buttons["zero_alt"].isEnabled()
        assert "/dev/cu.B" not in choices("telemetry") | choices("pointer")
        with pytest.raises(ValueError, match="both board"):
            c.connect("pointer", "/dev/cu.B")
        c.connect("pointer", "/dev/cu.C")
        c.tick()
        window.update_port_choices(force=True)
        assert "/dev/cu.C" not in choices("telemetry") | choices("uplink")
    finally:
        window.close()


@pytest.mark.parametrize("kwargs", [{"board_layout": "unknown"}, {"vehicle": "unknown"}])
def test_invalid_serial_topology_is_rejected_before_data_creation(qtbot, tmp_path, kwargs):
    path = tmp_path / "invalid"
    with pytest.raises(ValueError, match="Unknown"):
        Controller(path, **kwargs)
    assert not path.exists()


def test_unknown_serial_roles_cannot_add_workers(qtbot, tmp_path):
    c = Controller(tmp_path, board_layout="base")
    try:
        for operation in (lambda: c.connect("extra", "port"), lambda: c.disconnect("extra")):
            with pytest.raises(ValueError, match="Unknown serial role"):
                operation()
        assert set(c.workers) == {"telemetry", "uplink", "pointer"}
    finally:
        c.shutdown()


def test_uplink_serial_worker_preserves_command_raw_format_without_decoding_rx(qtbot, tmp_path, monkeypatch):
    class Port:
        def __init__(self):
            self.incoming = bytearray(frame(7))
            self.writes = []

        @property
        def in_waiting(self):
            return len(self.incoming)

        def open(self):
            pass

        def close(self):
            pass

        def cancel_read(self):
            pass

        def read(self, size):
            result = bytes(self.incoming[:size])
            del self.incoming[:size]
            if not result:
                time.sleep(0.005)
            return result

        def write(self, value):
            self.writes.append(value)
            return len(value)

    transport = Port()
    monkeypatch.setattr("rocket_gnc_monitor.devices.serial.Serial", lambda **_: transport)
    c = Controller(tmp_path / "app")
    recorder = SessionRecorder(tmp_path / "sessions", c.mission, "LIVE")
    events = []
    worker = SerialWorker("uplink", "fake", 1, lambda *event: events.append(event), recorder.raw)
    try:
        qtbot.waitUntil(lambda: any(event[2] == "connected" for event in events))
        with pytest.raises(ValueError, match="Polling belongs"):
            worker.set_polling(True)
        payload = rocket_packet("zero_alt")
        worker.send(payload, "command")
        qtbot.waitUntil(lambda: any(event[2] == "sent" for event in events))
        qtbot.waitUntil(lambda: any(event[2] == "rx" for event in events))
        assert transport.writes == [payload]
        assert worker.decoder is None
        assert not any(event[2] in {"sample", "stats"} for event in events)
    finally:
        worker.stop()
        recorder.close()
        c.shutdown()
    assert not recorder.error
    records = list(read_raw(recorder.path / "raw.bin"))
    assert len(records) == 1 and records[0][2:] == (4, payload)
    reader = SessionReader(recorder.path)
    try:
        assert reader.manifest["complete"] and reader.count == 0
        assert reader.db.execute("SELECT role FROM raw_index").fetchall() == [("telemetry_tx",)]
    finally:
        reader.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX pseudo-terminal transport test")
def test_three_real_serial_transports_keep_downlink_uplink_and_pointer_independent(qtbot, tmp_path):
    import pty

    c = Controller(tmp_path, board_layout="base")
    pairs = {role: pty.openpty() for role in c.serial_labels}
    try:
        for role, pair in pairs.items():
            c.connect(role, os.ttyname(pair[1]))
        qtbot.waitUntil(lambda: all(state == "Connected" for state in c.states.values()))
        c.set_polling(True)
        os.write(pairs["telemetry"][0], frame(123))
        os.write(pairs["uplink"][0], frame(999))
        qtbot.waitUntil(lambda: c.latest is not None)
        assert c.latest.sequence == 123 and c.stats["accepted"] == 1
        c.send_rocket("zero_alt")
        fd = pairs["uplink"][0]
        assert select.select([fd], [], [], 2)[0]
        assert os.read(fd, 100) == rocket_packet("zero_alt")
        assert not select.select([pairs["telemetry"][0]], [], [], 0.05)[0]
        c.point(90, 30)
        fd = pairs["pointer"][0]
        assert select.select([fd], [], [], 2)[0]
        assert os.read(fd, 100) == pointer_packet(90, 30)
        qtbot.waitUntil(lambda: not c.rocket_commands and c.pointer_pending is None)
        assert c.pointer_sent == (90, 30) and c.latest.sequence == 123
    finally:
        c.shutdown()
        for pair in pairs.values():
            for fd in pair:
                os.close(fd)

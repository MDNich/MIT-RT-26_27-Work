"""Application lifecycle; Qt sees bounded snapshots, never device or network reads."""

from __future__ import annotations
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import copy
import queue
from pathlib import Path
import time
import uuid
from PySide6.QtCore import QObject, QTimer, Signal
from .domain import Mission, demo_sample, pointing, target_position, to_enu
from .devices import SerialWorker
from .protocol import pointer_packet, validate_route
from .recording import SessionReader, SessionRecorder
from .trajectory import Trajectory, SimulationJob
from .media import VideoWorker


class Controller(QObject):
    changed = Signal()
    event = Signal(str)
    frame = Signal(bytes)
    task_done = Signal(str, object)

    def __init__(self, data_dir):
        super().__init__()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.mission = Mission()
        self.mode = "LIVE"
        self.latest = None
        self.history = deque(maxlen=6000)
        self.track = deque(maxlen=6000)
        self.reference = None
        self.workers = {"telemetry": None, "pointer": None}
        self.states = {"telemetry": "Disconnected", "pointer": "Disconnected"}
        self.last_live_received = None
        self.messages = queue.Queue(maxsize=16000)
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gnc")
        self.video_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-lifecycle")
        self.video_generation = 0
        self._video_backend = None
        self.futures = []
        self.generation = 0
        self.recorder = None
        self.reader = None
        self.video = None
        self.video_config = None
        self.simulation = None
        self.stats = dict(accepted=0, rejected=0, discarded=0, gaps=0)
        self.ui_drops = 0
        self.pointer_sent = None
        self.pointer_requested = None
        self.pointer_pending = None
        self.dispatched_commands = {}
        self.pointer_status = "Controls locked · connect the ground station"
        self.tracking = False
        self.last_tracking = 0
        self.demo_time = 0
        self.demo_sequence = 0
        self.replay_time = 0
        self.replay_playing = False
        self.replay_speed = 1.0
        self.flight_zero = 0
        self.time_aligned = False
        self.last_tick = time.monotonic()
        self._last_sample = 0
        self.alerts = {}
        self.alert_since = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)

    def log(self, name, data=None):
        self.event.emit(name)
        if self.recorder:
            self.recorder.event(name, data)

    def submit(self, name, function):
        future = self.executor.submit(function)
        future.source_mode = self.mode
        self.futures.append((name, future))

    @property
    def ground_connected(self):
        return (
            self.mode == "LIVE"
            and self.workers["telemetry"] is not None
            and self.states["telemetry"] == "Connected"
        )

    def require_ground_station(self):
        if self.mode == "LIVE" and not self.ground_connected:
            raise ValueError("Controls locked: connect the ground station first")

    def rocket_link_state(self, now=None):
        """Radio reception evidence; the protocol has no bidirectional handshake."""
        if self.mode != "LIVE":
            return self.mode, None
        if not self.ground_connected:
            return "DISCONNECTED", None
        if self.last_live_received is None:
            return "WAITING", None
        age = max(0, (time.monotonic() if now is None else now) - self.last_live_received)
        return ("RECEIVING" if age <= self.mission.freshness else "STALE"), age

    def switch_mode(self, mode):
        if mode not in {"LIVE", "DEMO", "REPLAY"}:
            raise ValueError("Unknown source mode")
        if mode == self.mode:
            return
        self.stop_recording()
        self.tracking = False
        for role in self.workers:
            self.disconnect(role)
        self.generation += 1
        self.mode = mode
        self.latest = None
        self.history.clear()
        self.track.clear()
        self.pointer_sent = self.pointer_pending = self.pointer_requested = None
        self.dispatched_commands.clear()
        self.alerts.clear()
        self.alert_since.clear()
        self.mission.pointer_calibrated = False
        self.states = {r: "Simulated" if mode == "DEMO" else "Disconnected" for r in self.workers}
        self.pointer_status = "Demo · no hardware" if mode == "DEMO" else "No measured feedback"
        self.replay_playing = False
        self.flight_zero = 0
        self.time_aligned = mode != "LIVE"
        self.demo_time = self.demo_sequence = 0
        self.stats = dict(accepted=0, rejected=0, discarded=0, gaps=0)
        if mode != "DEMO" and self.reference and self.reference.manifest.get("synthetic"):
            self.reference = None
        elif mode == "DEMO":
            self.reference = Trajectory.demo()
        self.stop_video()
        if mode == "DEMO":
            self.start_video("demo")
        self.log(f"Source changed to {mode}; physical pointer transport closed")
        self.changed.emit()

    def disconnect(self, role):
        worker = self.workers.get(role)
        self.workers[role] = None
        if worker:
            worker.stop_event.set()
            self.submit(f"disconnect:{role}", worker.stop)
        self.states[role] = "Disconnected"
        if role == "pointer":
            self.tracking = False
            self.pointer_pending = self.pointer_sent = None
            self.dispatched_commands.clear()
            self.mission.pointer_calibrated = False
        elif role == "telemetry":
            self.last_live_received = None
            if self.tracking or self.pointer_pending:
                self.hold("Ground station disconnected; controls locked")

    def connect(self, role, device):
        if self.mode != "LIVE":
            raise ValueError("Physical connections require LIVE mode")
        if not device:
            raise ValueError("Choose a serial device")
        normalize = lambda p: p.replace("/dev/tty.", "/dev/cu.").casefold()
        for other, worker in self.workers.items():
            if other != role and worker and normalize(worker.device) == normalize(device):
                raise ValueError("One serial device cannot serve both board roles")
        self.disconnect(role)
        self.generation += 1
        token = self.generation
        self.states[role] = "Connecting"

        def raw(source, data):
            worker = self.workers.get(role)
            if worker and worker.generation == token and self.recorder:
                self.recorder.raw(source, data)

        self.workers[role] = SerialWorker(role, device, token, self.enqueue, raw)
        self.log(f"Connecting {role}: {device}")

    def enqueue(self, generation, role, kind, data):
        worker = self.workers.get(role)
        if worker and worker.generation == generation and kind == "sample" and self.recorder:
            self.recorder.sample(data)
        try:
            self.messages.put_nowait((generation, role, kind, data))
        except queue.Full:
            self.ui_drops += 1

    def accept(self, sample, record=False):
        if self.ground_connected and sample.source == "LIVE":
            self.last_live_received = sample.received
        if sample.enu is None and self.mission.site_configured:
            try:
                sample.enu = to_enu(
                    *target_position(sample, self.mission),
                    (self.mission.latitude, self.mission.longitude, self.mission.altitude),
                )
            except ValueError:
                pass
        previous = self.latest
        if (
            self.mode == "LIVE"
            and previous
            and sample.details.get("boot_index") != previous.details.get("boot_index")
        ):
            self.time_aligned = False
            self.history.clear()
            self.track.clear()
            if self.tracking:
                self.hold("Flight computer restarted")
            self.log("Flight computer time epoch changed; realign flight time")
        if self.mode == "LIVE" and sample.phase == "Flight" and previous and previous.phase == "Preflight":
            self.flight_zero, self.time_aligned = sample.t, True
            self.log(
                "Flight zero aligned to received FLIGHT state transition", {"flight_zero": self.flight_zero}
            )
        self.latest = sample
        self.history.append(sample)
        if sample.enu:
            self.track.append(sample.enu)
        if record and self.recorder:
            self.recorder.sample(sample)

    def set_zero(self):
        self.require_ground_station()
        if not self.latest:
            raise ValueError("No telemetry sample available")
        self.flight_zero = self.latest.t
        self.time_aligned = True
        self.log("Flight time manually aligned", {"flight_zero": self.flight_zero})

    def point(self, azimuth, elevation):
        packet = pointer_packet(azimuth, elevation)
        self.pointer_requested = (azimuth, elevation)
        if self.mode == "REPLAY":
            raise ValueError("Replay cannot transmit pointer commands")
        if self.mode == "DEMO":
            self.pointer_sent = (azimuth, elevation)
            self.pointer_status = "Demo command applied · measured pose unavailable"
            self.log("Pointer command sent", {"angles": self.pointer_sent, "source": "DEMO"})
            return
        self.require_ground_station()
        if not self.mission.pointer_calibrated:
            raise ValueError("Establish the mount reference and confirm its operating envelope first")
        if self.pointer_pending:
            raise ValueError("Previous pointer command is awaiting dispatch")
        validate_route(self.pointer_sent, (azimuth, elevation), self.mission)
        worker = self.workers["pointer"]
        if not worker or self.states["pointer"] != "Connected":
            raise ValueError("Pointer board is disconnected")
        command_id = uuid.uuid4().hex
        self.dispatched_commands[command_id] = (azimuth, elevation)
        worker.send(packet, command_id)
        self.pointer_pending = (command_id, (azimuth, elevation))
        self.pointer_status = "Queued · not measured"
        self.log("Pointer command requested", {"id": command_id, "azimuth": azimuth, "elevation": elevation})

    def reference_zero(self):
        self.require_ground_station()
        if self.mode != "LIVE" or self.states["pointer"] != "Connected":
            raise ValueError("Connect the pointer in LIVE mode first")
        if self.pointer_pending:
            raise ValueError("A command is still awaiting dispatch")
        if not self.mission.pointer_calibrated:
            raise ValueError("Confirm that the mount is physically aligned with the configured zero")
        self.hold("Setting reference zero")
        command_id = uuid.uuid4().hex
        self.dispatched_commands[command_id] = (0.0, 0.0)
        self.workers["pointer"].send(pointer_packet(opcode=5), command_id)
        self.pointer_pending = (command_id, (0.0, 0.0))
        self.pointer_status = "Reference reset queued; no acknowledgment available"
        self.log("Pointer software reference reset requested")

    def hold(self, reason="Operator hold"):
        self.tracking = False
        worker = self.workers.get("pointer")
        if worker:
            try:
                _, _, command_id = worker.commands.get_nowait()
                self.dispatched_commands.pop(command_id, None)
            except queue.Empty:
                pass
        self.pointer_pending = None
        self.pointer_status = f"Hold: {reason}. Last commanded movement may continue."
        self.log(self.pointer_status)

    def jog(self, azimuth_delta=0, elevation_delta=0):
        if self.pointer_sent is None:
            raise ValueError("Send an absolute target or establish software zero before jogging")
        az, el = self.pointer_sent
        self.manual_point((az + azimuth_delta) % 360, el + elevation_delta)

    def manual_point(self, azimuth, elevation):
        if self.tracking:
            self.hold("Manual pointing")
        self.point(azimuth, elevation)

    def start_tracking(self):
        if self.mode == "REPLAY":
            raise ValueError("Replay cannot drive tracking")
        if self.mode == "LIVE":
            self.require_ground_station()
            self.tracking_target()
            if not self.mission.pointer_calibrated or self.states["pointer"] != "Connected":
                raise ValueError("Connect and calibrate the pointer first")
            if not self.mission.pointer_full_rotation:
                raise ValueError(
                    "Automatic tracking requires a verified continuous azimuth cable route; this board has no measured position"
                )
        self.tracking = True
        self.log("Tracking started" if self.mode == "LIVE" else "Demo tracking started")

    def tracking_target(self):
        if not self.latest or time.monotonic() - self.latest.received > self.mission.freshness:
            raise ValueError("Rocket position is stale")
        if self.mode == "DEMO":
            e, n, u = self.latest.enu
            import math

            return math.degrees(math.atan2(e, n)) % 360, min(
                80, math.degrees(math.atan2(u, max(10, math.hypot(e, n))))
            )
        if self.latest.source != "LIVE":
            raise ValueError("Tracking needs a live source")
        origin = (
            self.mission.pointer_latitude,
            self.mission.pointer_longitude,
            self.mission.pointer_altitude,
        )
        az, el = pointing(target_position(self.latest, self.mission), origin)
        return (az + self.mission.pointer_az_offset) % 360, el + self.mission.pointer_el_offset

    def start_recording(self, parent):
        self.require_ground_station()
        if self.mode == "REPLAY":
            raise ValueError("Replay sessions are read-only")
        if self.recorder:
            raise ValueError("Already recording")
        self.recorder = SessionRecorder(parent, self.mission, self.mode, self.flight_zero, self.time_aligned)
        if self.reference:
            self.reference.save(self.recorder.path / "reference.csv")
        self.log("Recording started", {"mode": self.mode})
        if self.video_config:
            kind, source = self.video_config
            self.start_video(kind, source)
        return self.recorder.path

    def stop_recording(self):
        if self.recorder:
            recorder, self.recorder = self.recorder, None
            recorder.event("Recording stopped")
            video_close = None
            if self.video_config:
                kind, source = self.video_config
                video_close = self.start_video(kind, source)

            def close_recording():
                if video_close:
                    video_close.result()
                return recorder.close(), recorder.error, str(recorder.path)

            self.submit("recording_closed", close_recording)

    def open_replay(self, path):
        reader = SessionReader(path)
        self.switch_mode("REPLAY")
        if self.reader:
            self.reader.close()
        self.reader = reader
        values = reader.manifest.get("mission", {})
        self.mission = Mission(
            **{k: v for k, v in values.items() if k in Mission.__dataclass_fields__}
        ).validate()
        self.mission.pointer_calibrated = False
        self.flight_zero = reader.manifest.get("flight_zero", 0)
        ref = reader.path / "reference.csv"
        self.reference = Trajectory.load(ref) if ref.exists() else None
        self.seek(0)
        self.log(
            f"Replay loaded: {reader.count} samples; "
            + ("complete" if reader.manifest.get("complete") else "recovered/incomplete")
        )

    def seek(self, elapsed):
        if not self.reader:
            return
        self.replay_time = max(0, min(elapsed, self.reader.duration))
        self.history.clear()
        self.track.clear()
        self.latest = None
        self.pointer_sent = None
        self.flight_zero = self.reader.manifest.get("flight_zero", 0)
        self.time_aligned = self.reader.manifest.get("time_aligned", True)
        for _, event in self.reader.events(self.replay_time):
            self.apply_replay_event(event)
        for _, sample in self.reader.between(max(-1, self.replay_time - 120), self.replay_time):
            sample.received = time.monotonic()
            self.accept(sample)
        self.replay_video()
        self.changed.emit()

    def apply_replay_event(self, event):
        if "flight_zero" in event["data"]:
            self.flight_zero = event["data"]["flight_zero"]
            self.time_aligned = True
        if event["name"] == "Pointer command sent":
            self.pointer_sent = tuple(event["data"]["angles"])
            self.pointer_status = "Recorded command · measured pose unavailable"

    def acknowledge_alerts(self):
        for key, alert in self.alerts.items():
            if not alert["acknowledged"]:
                alert["acknowledged"] = True
                self.log("Alert acknowledged", {"key": key, "message": alert["message"]})

    def update_alerts(self, now):
        if self.mode != "LIVE":
            self.alerts.clear()
            self.alert_since.clear()
            return
        stale = not self.latest or now - self.latest.received > self.mission.freshness
        battery = self.latest.battery if self.latest else None
        threshold = self.mission.low_battery + (0.3 if "battery" in self.alerts else 0)
        conditions = {
            "telemetry": (stale, "Telemetry stale / absent", 0),
            "battery": (not stale and battery is not None and battery < threshold, "Low battery", 1),
            "recording": (bool(self.recorder and self.recorder.error), "Recording fault / loss", 0),
            "video": (
                bool(
                    self.video
                    and (self.video.error or (self.video.last_frame and now - self.video.last_frame > 2))
                ),
                "Video ended / stale",
                1,
            ),
        }
        for key, (active, message, dwell) in conditions.items():
            if active:
                since = self.alert_since.setdefault(key, now)
                if now - since >= dwell and key not in self.alerts:
                    self.alerts[key] = {"message": message, "acknowledged": False}
                    self.log("Alert active: " + message, {"key": key})
            else:
                self.alert_since.pop(key, None)
                if self.alerts.pop(key, None):
                    self.log("Alert cleared: " + message, {"key": key})

    def replay_video(self):
        if not self.reader:
            return
        import csv

        events = [
            (t, e)
            for t, e in self.reader.events(self.reader.duration)
            if e["name"] == "Video recording started"
        ]
        eligible = [(t, e) for t, e in events if t <= self.replay_time - self.mission.video_offset]
        if not eligible:
            self.stop_video()
            return
        start, event = eligible[-1]
        directory_name = event["data"].get("directory", "video")
        directory = self.reader.path / Path(directory_name).name
        listing = directory / "segments.csv"
        if not listing.exists():
            self.stop_video()
            return
        cursor = self.replay_time - start - self.mission.video_offset
        with listing.open(newline="") as handle:
            for name, begin, end in csv.reader(handle):
                if float(begin) <= cursor < float(end):
                    # Ignore directory components from imported session manifests.
                    path = directory / Path(name).name
                    if path.is_file():
                        self.start_video("file", str(path), cursor - float(begin))
                    return
        self.stop_video()

    def start_video(self, kind, source="", seek=0):
        self.video_generation += 1
        token = self.video_generation
        self.video = None
        self.video_config = (kind, source)
        directory = self.recorder.path / "video" if self.recorder else None
        if self.recorder:
            # A new recording directory avoids overwriting previous segments on reconnect.
            if directory.exists():
                directory = self.recorder.path / ("video_" + uuid.uuid4().hex[:6])
            self.log("Video recording started", {"directory": directory.name, "kind": kind})
        speed = self.replay_speed if self.mode == "REPLAY" else 1.0
        single_frame = self.mode == "REPLAY" and not self.replay_playing

        def open_video():
            if self._video_backend:
                self._video_backend.stop()
                self._video_backend = None
            if token != self.video_generation:
                return token, None
            self._video_backend = VideoWorker(kind, source, directory, seek, speed, single_frame)
            return token, self._video_backend

        future = self.video_executor.submit(open_video)
        self.futures.append(("video_open", future))
        return future

    def stop_video(self):
        self.video_generation += 1
        self.video = None
        self.video_config = None

        def close_video():
            if self._video_backend:
                self._video_backend.stop()
                self._video_backend = None

        self.futures.append(("video_closed", self.video_executor.submit(close_video)))

    def run_simulation(self):
        if self.simulation:
            raise ValueError("A simulation is already running")
        mission = copy.deepcopy(self.mission).validate()
        if not mission.site_configured:
            raise ValueError("Configure the launch site before simulation")
        job = SimulationJob(mission, self.data_dir / "simulation" / uuid.uuid4().hex)
        self.simulation = job
        self.submit("simulation", job.run)
        self.log("OpenRocket nominal simulation started")

    def tick(self):
        now = time.monotonic()
        dt, self.last_tick = min(now - self.last_tick, 0.3), now
        for _ in range(2000):
            try:
                generation, role, kind, data = self.messages.get_nowait()
            except queue.Empty:
                break
            worker = self.workers.get(role)
            if not worker or worker.generation != generation or self.mode != "LIVE":
                continue
            if kind == "sample" and self.states[role] == "Connected":
                self.accept(data)
            elif kind == "stats":
                self.stats = data
            elif kind == "connected":
                self.states[role] = "Connected"
                self.log(f"{role.title()} connected")
            elif kind in {"error", "disconnected"}:
                self.states[role] = "Disconnected"
                self.log(f"{role.title()}: {data}")
                if role == "telemetry":
                    self.last_live_received = None
                if self.tracking or self.pointer_pending:
                    self.hold(f"{role} unavailable")
                if role == "pointer":
                    self.pointer_sent = self.pointer_pending = None
                    self.mission.pointer_calibrated = False
            elif kind == "sent" and data in self.dispatched_commands:
                self.pointer_sent = self.dispatched_commands.pop(data)
                if self.pointer_pending and data == self.pointer_pending[0]:
                    self.pointer_pending = None
                    self.pointer_status = "Sent · acknowledgment / measured pose unavailable"
                self.log("Pointer command sent", {"id": data, "angles": self.pointer_sent})
            elif kind == "expired":
                self.dispatched_commands.pop(data, None)
                self.hold("Queued command expired")
            elif kind == "rx":
                self.log("Pointer RX (unstructured): " + data[:140])
        if self.mode == "DEMO":
            self.demo_time += dt
            if now - self._last_sample >= 0.05:
                self.demo_sequence += 1
                self.accept(
                    demo_sample(self.demo_time, self.demo_sequence, self.mission.canard_count), record=True
                )
                self._last_sample = now
        elif self.mode == "REPLAY" and self.reader and self.replay_playing:
            begin = self.replay_time
            self.replay_time = min(self.reader.duration, begin + dt * self.replay_speed)
            for _, event in self.reader.events(self.replay_time, begin):
                self.apply_replay_event(event)
                self.event.emit("REPLAY · " + event["name"])
            for _, sample in self.reader.between(begin, self.replay_time):
                sample.received = now
                self.accept(sample)
            if self.replay_time >= self.reader.duration:
                self.replay_playing = False
                self.stop_video()
            elif self.video and self.video.error == "Video ended":
                self.replay_video()
        if self.tracking and now - self.last_tracking >= 0.2:
            self.last_tracking = now
            try:
                target = self.tracking_target()
                if not self.pointer_pending:
                    self.point(*target)
            except (ValueError, queue.Full) as exc:
                self.hold(str(exc))
        if self.video:
            frame = None
            while not self.video.frames.empty():
                try:
                    frame = self.video.frames.get_nowait()
                except queue.Empty:
                    break
            if frame:
                self.frame.emit(frame)
        for name, future in self.futures[:]:
            if future.done():
                self.futures.remove((name, future))
                try:
                    result = future.result()
                    if name in {"weather", "reference", "simulation"} and future.source_mode != self.mode:
                        raise ValueError(
                            "Completed result belongs to the previous source mode; load it explicitly if needed"
                        )
                    if name == "simulation" and self.simulation:
                        fields = (
                            "latitude",
                            "longitude",
                            "altitude",
                            "altitude_msl",
                            "model",
                            "motor_files",
                            "wind",
                            "rail_length",
                            "rail_tilt",
                            "rail_heading",
                            "seed",
                            "simulation_index",
                        )
                        if any(
                            getattr(self.simulation.mission, k) != getattr(self.mission, k) for k in fields
                        ):
                            raise ValueError(
                                "Simulation inputs changed while running; result remains in its job folder"
                            )
                    if name == "video_open":
                        token, worker = result
                        if token == self.video_generation:
                            self.video = worker
                    self.task_done.emit(name, result)
                except Exception as exc:
                    self.log(f"{name}: {exc}")
                    self.task_done.emit(name, exc)
                if name == "simulation":
                    self.simulation = None
        self.update_alerts(now)
        self.changed.emit()

    def shutdown(self):
        self.timer.stop()
        for role in self.workers:
            worker = self.workers[role]
            self.workers[role] = None
            if worker:
                worker.stop()
        self.stop_video()
        self.video_executor.shutdown(wait=True, cancel_futures=False)
        if self.simulation:
            self.simulation.cancel()
        if self.recorder:
            self.recorder.close()
        if self.reader:
            self.reader.close()
        # A queued recorder close must finish even if the operator closes the app immediately.
        self.executor.shutdown(wait=True, cancel_futures=False)

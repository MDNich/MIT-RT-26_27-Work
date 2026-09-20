"""Independent bounded serial workers. Telemetry transport has no write API."""

from __future__ import annotations
import queue
import threading
import time
import serial
from serial.tools import list_ports
from .protocol import ZephyrusDecoder


def ports():
    return [
        dict(
            device=p.device,
            description=p.description,
            serial=p.serial_number,
            identity=f"{p.vid}:{p.pid}:{p.serial_number}"
            if p.serial_number
            else p.device.replace("/dev/tty.", "/dev/cu."),
        )
        for p in list_ports.comports()
    ]


class SerialWorker:
    def __init__(self, role, device, generation, emit, raw, baud=115200):
        if role not in {"telemetry", "pointer"}:
            raise ValueError("Unknown serial role")
        self.role, self.device, self.generation = role, device, generation
        self.emit, self.raw, self.baud = emit, raw, baud
        self.stop_event = threading.Event()
        self.commands = queue.Queue(maxsize=1)
        self.decoder = ZephyrusDecoder()
        self.connection = None
        self.thread = threading.Thread(target=self.run, name=f"{role}-serial", daemon=True)
        self.thread.start()

    def send(self, payload, command_id):
        if self.role != "pointer" or self.stop_event.is_set():
            raise ValueError("Transport is not an active pointer")
        # Never silently replace manual commands. Tracking sends only after its preceding dispatch.
        self.commands.put_nowait((time.monotonic() + 0.5, bytes(payload), command_id))

    def stop(self):
        self.stop_event.set()
        if self.connection:
            try:
                self.connection.cancel_read()
            except (AttributeError, OSError):
                pass
        self.thread.join(timeout=1.5)

    def message(self, kind, data):
        self.emit(self.generation, self.role, kind, data)

    def run(self):
        try:
            self.connection = serial.Serial(port=None, baudrate=self.baud, timeout=0.05, write_timeout=0.2)
            self.connection.dtr = False
            self.connection.rts = False
            self.connection.port = self.device
            self.connection.open()
            self.message("connected", self.device)
            while not self.stop_event.is_set():
                if self.role == "pointer":
                    try:
                        expires, payload, command_id = self.commands.get_nowait()
                    except queue.Empty:
                        pass
                    else:
                        if time.monotonic() > expires or self.stop_event.is_set():
                            self.message("expired", command_id)
                        else:
                            written = self.connection.write(payload)
                            self.raw("pointer_tx", payload[:written])
                            if written != len(payload):
                                raise IOError("Incomplete pointer write; command outcome uncertain")
                            self.message("sent", command_id)
                chunk = self.connection.read(min(max(self.connection.in_waiting, 1), 4096))
                if chunk:
                    self.raw(self.role + "_rx", chunk)
                    if self.role == "telemetry":
                        for sample in self.decoder.feed(chunk):
                            self.message("sample", sample)
                        self.message(
                            "stats",
                            {
                                key: getattr(self.decoder, key)
                                for key in ("accepted", "rejected", "discarded", "gaps")
                            },
                        )
                    else:
                        self.message("rx", chunk.hex(" "))
        except Exception as exc:
            self.message("error", str(exc))
        finally:
            if self.connection:
                self.connection.close()
            self.message("disconnected", self.device)

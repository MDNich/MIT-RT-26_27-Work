"""Capture reference outputs from legacy class methods using in-memory serial only.

Usage: .venv/bin/python scripts/capture_legacy_reference.py /path/to/ground_station
No serial constructors, GUI, or module-level legacy code are executed.
"""

import ast
import contextlib
import csv
from enum import Enum
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import numpy as np

source = Path(sys.argv[1])
root = Path(__file__).resolve().parents[1]


def classes(filename, names):
    tree = ast.parse((source / filename).read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in names]
    # Exclude physical I/O and file-opening methods even though none are called.
    for node in nodes:
        node.body = [
            n
            for n in node.body
            if not isinstance(n, ast.FunctionDef)
            or n.name
            not in {
                "connect",
                "disconnect",
                "connect_serial",
                "disconnect_serial",
                "log_data_start",
                "log_data_stop",
            }
        ]
    environment = dict(
        np=np, struct=struct, time=time, os=os, Enum=Enum, HARDWARE_PORT="IN-MEMORY", gps_lat=0, gps_lon=0
    )
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), environment)
    return environment


class Wire(io.BytesIO):
    is_open = True

    @property
    def in_waiting(self):
        return len(self.getvalue()) - self.tell()


with contextlib.redirect_stdout(io.StringIO()):
    reference = classes("rocket.py", ["state", "rocket"])
    rocket = reference["rocket"]()
    rocket.debug = False
    commands = []
    arguments = {
        "advance_state": list(range(1, 7)),
        "set_vtx_power": list(range(4)),
        "set_roll_control_servo_angle": [-50.5, 0, 24.25, 1.234567],
        "set_airbrakes_angle": [-12.5, 0, 60, 1.234567],
        "update_converters": [[bool(mask & (1 << i)) for i in range(6)] for mask in range(64)],
        "bmsprotections": [0, 1],
    }
    for name in ["arm_pyros", "fire_pyros", "disarm_pyros"]:
        arguments[name] = [[i] for i in range(6)] + [[0, 2, 5], list(range(6))]
    for name in [
        "zero_servos",
        "zero_pitchYawRoll",
        "zero_roll",
        "zero_alt",
        "zero_velo",
        "pd_activate",
        "EMERG_DEPLOY_PISTON",
        "EMERG_DEPLOY_BP_WELLS",
        "EMERG_DEPLOY_TD",
        "EMERG_DEPLOY_ALL",
    ]:
        arguments[name] = [None]
    for name, values in arguments.items():
        for value in values:
            rocket.ser = Wire()
            if name == "advance_state":
                rocket.state = reference["state"](value - 1)
            getattr(rocket, name)(*([] if value is None or name == "advance_state" else [value]))
            commands.append(dict(command=name, value=value, hex=rocket.ser.getvalue().hex()))
    pointer = classes("pointer.py", ["pointer"])["pointer"]()
    pointer.isConnected = True
    pointer_commands = []
    for name, angles in [
        ("send_angles", [90, 45]),
        ("send_angles", [-90.5, 91.25]),
        ("send_angles", [720, -135]),
        ("up", None),
        ("down", None),
        ("left", None),
        ("right", None),
        ("zero", None),
    ]:
        pointer.ser = Wire()
        getattr(pointer, name)(*(angles or []))
        pointer_commands.append(dict(command=name, angles=angles, hex=pointer.ser.getvalue().hex()))
    pointing = []
    for origin, target in [
        ([42.36037, -71.09355, 52.3], [42.366, -71.091, 803.5]),
        ([-33.91234, 151.23456, -10], [-33.95, 151.20, 200]),
        ([0.12345, 179.99999, 10], [0.124, -179.98, 300]),
    ]:
        pointer.updateGPS(*origin)
        pointing.append(dict(origin=origin, target=target, angles=list(pointer.calc_angles(*target))))
    tree = ast.parse((source / "rocket.py").read_text())
    header = next(
        ast.literal_eval(n.value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "header" for t in n.targets)
    )
    p = bytearray(128)
    struct.pack_into("<H", p, 0, 0b111001001110)
    p[2:4] = bytes([0b101001, 0b001010])
    p[4:10] = bytes([1, 10, 25, 100, 200, 255])
    p[10:16] = sum(v << (12 * i) for i, v in enumerate([1501, 2001, 1203, 1777])).to_bytes(6, "little")
    for off, val in [(16, 123456), (19, -98765), (22, 12800)]:
        p[off : off + 3] = val.to_bytes(3, "little", signed=True)
    struct.pack_into("<hhhBii", p, 25, 327, -234, 150, 3, 423601234, -710932345)
    struct.pack_into("<fIIB", p, 40, 431.25, 1234, 2345, 11)
    p[53:56] = (7501234).to_bytes(3, "little")
    p[56:59] = (9601234).to_bytes(3, "little")
    struct.pack_into("<fBfffHHIHb", p, 59, 431.75, 3, 1.25, -2.5, 32.5, 1500, 1600, 123456, 321, -23)
    struct.pack_into("<hhhhBBB", p, 87, 3789, 3498, 4123, -1234, 61, 0b01000101, 0b11001010)
    struct.pack_into("<6h", p, 98, 1875, 2062, 3125, 4625, 5250, 17500)
    struct.pack_into("<6h", p, 110, 100, -200, 300, 400, -500, 600)
    struct.pack_into("<f", p, 122, -12.75)
    p[127] = sum(p[:127]) % 256
    g = struct.pack("<bBiii", -19, 3, 423601299, -710933499, -12345)
    good_frame = b"\xab\xab" + p + g
    bad_frame = bytearray(good_frame)
    bad_frame[2 + 127] ^= 1
    decoded = []
    for packet, rejected in [(good_frame, False), (bytes(bad_frame), True)]:
        rocket = reference["rocket"]()
        rocket.debug = False
        rocket.ser = Wire(packet)
        rocket.logging = True
        with (
            tempfile.TemporaryFile(mode="w+", newline="") as good,
            tempfile.TemporaryFile(mode="w+", newline="") as bad,
        ):
            rocket.file, rocket.file_badpackets = good, bad
            rocket.csv_writer, rocket.csv_writer_badpackets = csv.writer(good), csv.writer(bad)
            rocket.telemetry_downlink_update()
            handle = bad if rejected else good
            handle.seek(0)
            row = next(csv.reader(handle))
            decoded.append(dict(hex=packet.hex(), rejected=rejected, values=dict(zip(header, row))))
    shortcuts = []
    tree = ast.parse((source / "UI.py").read_text())
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "setShortcut":
            shortcuts.append(ast.literal_eval(n.args[0].args[0]))
    result = dict(
        source_hashes={
            name: hashlib.sha256((source / name).read_bytes()).hexdigest()
            for name in ["UI.py", "rocket.py", "pointer.py"]
        },
        commands=commands,
        pointer_commands=pointer_commands,
        pointing=pointing,
        csv_fields=header,
        telemetry=decoded,
        shortcuts=shortcuts,
    )
output = root / "tests/fixtures/legacy_reference.json"
output.parent.mkdir(exist_ok=True)
output.write_text(
    json.dumps(result, indent=2, default=lambda v: v.item() if isinstance(v, np.generic) else v) + "\n"
)
print(
    f"Captured {len(commands)} rocket vectors, {len(pointer_commands)} pointer vectors, all CSV columns and {len(shortcuts)} shortcuts to {output}"
)

"""Import the audited legacy monitor's CSV columns without executing field text."""

from __future__ import annotations
import ast
import csv
import hashlib
import math
from pathlib import Path
import shutil
from .domain import Sample, finite, write_json
from .recording import SessionRecorder


def numeric_list(text):
    if len(text) > 4096:
        raise ValueError("Legacy numeric array too large")

    def value(node):
        if isinstance(node, ast.Constant) and finite(node.value):
            return float(node.value)
        if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) <= 32:
            return [value(item) for item in node.elts]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            result = value(node.operand)
            return -result if isinstance(node.op, ast.USub) else result
        # NumPy 2 scalar reprs appeared inside lists written by the old monitor.
        if (
            isinstance(node, ast.Call)
            and not node.keywords
            and len(node.args) == 1
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {"np", "numpy"}
            and node.func.attr in {"float32", "float64", "int32", "int64"}
        ):
            return value(node.args[0])
        raise ValueError("Unsupported legacy numeric literal")

    result = value(ast.parse(text, mode="eval").body)
    if not isinstance(result, list) or not all(finite(item) for item in result):
        raise ValueError("Expected a legacy numeric list")
    return result


def import_legacy(path, parent, mission):
    source = Path(path)
    if source.stat().st_size > 200_000_000:
        raise ValueError("Legacy CSV exceeds 200 MB")
    if "badpackets" in source.name.lower():
        raise ValueError("Known bad-packet logs cannot be promoted to telemetry samples")
    recorder = None
    try:
        with source.open(newline="", encoding="utf-8-sig") as handle:
            rows = csv.DictReader(handle)
            required = {
                "timestamp",
                "flight_time",
                "pktnum",
                "barofilteredalt",
                "gpsalt",
                "lat",
                "lon",
                "state",
                "servos",
            }
            if not required.issubset(rows.fieldnames or []):
                raise ValueError(
                    "Not the documented Zephyrus CSV layout; missing "
                    + ", ".join(sorted(required - set(rows.fieldnames or [])))
                )
            recorder = SessionRecorder(parent, mission, "LEGACY_CSV", time_aligned=False)
            first = None
            previous = -math.inf
            previous_phase = None
            count = 0
            phase_names = {
                "GROUND_TESTING": "Ground testing",
                "PRE_FLIGHT": "Preflight",
                "FLIGHT": "Flight",
                "POST_APOGEE": "Post-apogee",
                "MAIN": "Main",
                "END": "End",
            }
            for row in rows:

                def number(key):
                    try:
                        v = float(row.get(key, ""))
                        return v if math.isfinite(v) else None
                    except (ValueError, TypeError):
                        return None

                timestamp, ticks, sequence = number("timestamp"), number("flight_time"), number("pktnum")
                if any(v is None for v in (timestamp, ticks, sequence)) or timestamp < previous:
                    raise ValueError(f"Invalid/nonmonotonic CSV time at row {count + 2}")
                if first is None:
                    first = timestamp
                elapsed = timestamp - first
                previous = timestamp
                arrays = {}
                for key in ("servos", "gyro", "accelerometer", "cell_voltages"):
                    try:
                        arrays[key] = numeric_list(row.get(key, "[]"))
                    except (ValueError, SyntaxError, TypeError):
                        arrays[key] = []
                attitude = [number(key) for key in ("roll_gyro_int", "pitch_gyro_int", "yaw_gyro_int")]
                fix = number("gps_fix")
                lat, lon = number("lat"), number("lon")
                valid = lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180
                phase = phase_names.get(row["state"].split(".")[-1], "Unknown")
                sample = Sample(
                    t=ticks / 1000,
                    sequence=int(sequence),
                    source="LEGACY_CSV",
                    received=recorder.start + elapsed,
                    utc=timestamp,
                    altitude=number("barofilteredalt"),
                    velocity=number("accel_integrated_velo"),
                    latitude=lat if valid else None,
                    longitude=lon if valid else None,
                    gps_fix=int(fix) if fix is not None and valid else 0,
                    gps_altitude=number("gpsalt"),
                    battery=sum(arrays["cell_voltages"]) if len(arrays["cell_voltages"]) == 3 else None,
                    rssi=number("rssi"),
                    phase=phase,
                    attitude=attitude if all(finite(v) for v in attitude) else None,
                    rates=arrays["gyro"] if len(arrays["gyro"]) == 3 else None,
                    acceleration=arrays["accelerometer"] if len(arrays["accelerometer"]) == 3 else None,
                    actuators={
                        f"Legacy servo {i + 1}": {"drive": v} for i, v in enumerate(arrays["servos"][:4])
                    },
                    details={
                        "legacy_csv": row,
                        "attitude_kind": "Legacy integrated rotation · CSV import",
                        "quality": "Imported decoded CSV; raw packet checksum unavailable",
                    },
                )
                if recorder.error:
                    raise ValueError(recorder.error)
                # File import may wait for disk; unlike live acquisition it must never drop rows.
                recorder.queue.put(("sample", sample.received, sample.to_dict()), timeout=5)
                if phase == "Flight" and previous_phase == "Preflight":
                    recorder.queue.put(
                        (
                            "event",
                            sample.received,
                            {"name": "Imported flight transition", "data": {"flight_zero": sample.t}},
                        ),
                        timeout=5,
                    )
                previous_phase = phase
                count += 1
            if not count:
                raise ValueError("CSV contains no samples")
        recorder.close()
        if recorder.error:
            raise ValueError(recorder.error)
        shutil.copyfile(source, recorder.path / "legacy-source.csv")
        with source.open("rb") as file:
            digest = hashlib.file_digest(file, "sha256").hexdigest()
        recorder.manifest.update(
            duration=previous - first,
            started_utc=first,
            imported_rows=count,
            imported_source_sha256=digest,
            raw_packets_available=False,
        )
        write_json(recorder.path / "manifest.json", recorder.manifest)
        return recorder.path
    except Exception:
        if recorder:
            recorder.error = "Legacy import incomplete"
            recorder.close()
            recorder.manifest.update(complete=False, error=recorder.error)
            write_json(recorder.path / "manifest.json", recorder.manifest)
        raise

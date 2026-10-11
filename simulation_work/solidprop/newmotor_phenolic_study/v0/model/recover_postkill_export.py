"""Recover one accepted MAPDL step rejected only by stale POST1 dead rows.

This is deliberately narrow.  It refuses any missing live field, any foreign ID,
any mismatch between element and energy exports, or any coupling error other
than the known post-EKILL export rejection.  The failed runtime must already
have been preserved separately before this tool is run.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


KNOWN_ERROR = "Missing, duplicate or resurrected solid fields"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".new")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def import_file(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        raise RuntimeError("Recovery is write-enabled; pass --apply explicitly.")

    root = args.root.resolve()
    evidence = args.evidence.resolve()
    if root == evidence or not root.is_dir() or not evidence.is_dir():
        raise RuntimeError("Working runtime and preserved evidence must be distinct directories.")

    coupler = import_file(root / "coupler.py", "v0_recovery_coupler")
    package_check = import_file(root / "package_check.py", "v0_recovery_package_check")
    state_before = load(root / "state.json")
    pending = load(root / "pending.json")
    config = load(root / "config.json")
    mesh = load(root / "mesh_map.json")
    error_text = (root / "coupler_error.txt").read_text(encoding="utf-8")

    if KNOWN_ERROR not in error_text:
        raise RuntimeError("This is not the known post-EKILL POST1 export rejection.")
    if state_before["status"] != "RUNNING":
        raise RuntimeError("Expected the failed controller state to remain RUNNING.")
    if pending["index"] != state_before["index"] + 1:
        raise RuntimeError("Pending index is not the next macro-step.")
    observed = float((root / "observed_time.txt").read_text(encoding="utf-8").strip())
    if abs(observed - pending["target"]) > 1e-8:
        raise RuntimeError("Observed MAPDL time does not match the pending target.")

    fields = coupler.read_rows(root / "element_fields.txt")
    energy = coupler.read_rows(root / "energy_fields.txt")
    dead = {str(face["element"]) for row in mesh["rows"][: pending["layer"]] for face in row}
    defined = set(mesh["elements"])
    expected = defined - dead
    field_ids = set(fields)
    energy_ids = set(energy)
    if field_ids != energy_ids or not expected.issubset(field_ids):
        raise RuntimeError("Live solver exports are incomplete or inconsistent.")
    if field_ids - expected != dead:
        raise RuntimeError("The surplus export IDs are not exactly the controller-declared dead elements.")

    restart_files = [root / f"file{rank}.r001" for rank in range(config["ranks"])]
    if any(not path.is_file() or path.stat().st_size == 0 for path in restart_files):
        raise RuntimeError("Latest distributed restart generation is incomplete.")
    mtimes = [path.stat().st_mtime for path in restart_files]
    if max(mtimes) - min(mtimes) > 5:
        raise RuntimeError("Distributed restart timestamps are not coherent.")

    old_manifest = load(evidence / "input_manifest.json")
    old_coupler_hash = sha256(evidence / "coupler.py")
    if old_manifest.get("coupler.py") != old_coupler_hash:
        raise RuntimeError("Preserved evidence no longer matches its sealed manifest.")

    subprocess.run(
        [sys.executable, "-B", str(root / "coupler.py"), "accept", "--root", str(root)],
        check=True,
        cwd=root,
    )
    state_after = load(root / "state.json")
    if state_after["index"] != pending["index"] or abs(state_after["time_s"] - observed) > 1e-8:
        raise RuntimeError("Recovered acceptance did not publish the expected checkpoint.")
    state_after["status"] = "PAUSED_AT_CHECKPOINT"
    atomic_json(root / "state.json", state_after)

    recovery_dir = root / "recovery_evidence"
    recovery_dir.mkdir(exist_ok=False)
    shutil.move(root / "coupler_error.txt", recovery_dir / "coupler_error_original.txt")
    if (root / "PREFLIGHT_OK.txt").exists():
        shutil.move(root / "PREFLIGHT_OK.txt", recovery_dir / "PREFLIGHT_OK_before_recovery.txt")

    new_manifest = package_check.hashes()
    atomic_json(root / "input_manifest.json", new_manifest)
    provenance = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "reason": "MAPDL 2026 R1 POST1 exported stale rows for controller-declared EKILLed elements",
        "preserved_failed_runtime": str(evidence),
        "working_runtime": str(root),
        "known_error_sha256": sha256(recovery_dir / "coupler_error_original.txt"),
        "old_coupler_sha256": old_coupler_hash,
        "new_coupler_sha256": sha256(root / "coupler.py"),
        "state_before": {key: state_before[key] for key in ("index", "time_s", "status", "layer")},
        "state_after": {key: state_after[key] for key in ("index", "time_s", "status", "layer")},
        "pending_target": pending["target"],
        "defined_elements": len(defined),
        "live_elements": len(expected),
        "dead_rows_ignored": len(dead),
        "restart_generation": {
            path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in restart_files
        },
        "old_input_manifest": old_manifest,
        "new_input_manifest": new_manifest,
    }
    atomic_json(root / "RECOVERY_PROVENANCE.json", provenance)
    print(f"RECOVERY_READY index={state_after['index']} time={state_after['time_s']:.16g} dead_rows={len(dead)}")


if __name__ == "__main__":
    main()

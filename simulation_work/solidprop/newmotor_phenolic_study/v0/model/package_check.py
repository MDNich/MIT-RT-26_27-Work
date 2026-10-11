"""Seal or verify immutable solver inputs; runtime results are excluded."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FILES = (
    "config.json", "coupler.py", "model_base.inp", "mesh_map.json",
    "material_v0.apdl", "export_fields.mac", "run_v0.inp", "resume_v0.inp",
    "couple.cmd", "preflight_v0.inp", "launch_v0.ps1", "request_pause.ps1",
    "status_v0.ps1", "usermatth.F", "usermatthLib.dll",
)


def hashes() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal", action="store_true")
    args = parser.parse_args()
    path = ROOT / "input_manifest.json"
    actual = hashes()
    if args.seal:
        if (ROOT / "state.json").exists():
            raise RuntimeError("Cannot reseal inputs after a calculation has started.")
        path.write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
        print("INPUTS_SEALED_NO_SOLVE")
    else:
        expected = json.loads(path.read_text(encoding="utf-8"))
        if expected != actual:
            raise RuntimeError("Input package changed after sealing; create a new runtime directory and repeat preflight.")
        print("INPUT_PACKAGE_HASHES_MATCH_NO_SOLVE")


if __name__ == "__main__":
    main()

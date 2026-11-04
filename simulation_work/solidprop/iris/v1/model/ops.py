"""Host/guest operations and the user's hard storage limits (stdlib only)."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import time
import fcntl
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
TMP = ROOT / "ansystmp"
VM = "{e7540578-be7d-4ee0-9a40-8aa94dcb9efd}"
UNC = r"\\Mac\Home\Developer\MIT-RT-26_27-Work\simulation_work\solidprop\iris\v1"
MAC_FLOOR = 400_000_000_000
WINDOWS_FLOOR = 10_000_000_000

class StorageLimitError(RuntimeError):
    pass

def utc():
    return datetime.now(timezone.utc).isoformat()

def atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".new")
    temp.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")
    temp.replace(path)

def host_check(reserve=0):
    free = shutil.disk_usage(ROOT).free
    if free < MAC_FLOOR + reserve:
        raise StorageLimitError(f"STOP: Mac free bytes {free} below required {MAC_FLOOR + reserve}")
    if (TMP / "STOP_WORK.json").exists():
        raise RuntimeError("Storage stop is latched; no automatic resume.")
    return free

def guest(script, timeout=45):
    """Short encoded commands avoid shell quoting; long scripts use the share."""
    encoded = base64.b64encode(script.encode("utf-16le")).decode()
    cmd = ["prlctl", "exec", VM, "powershell.exe", "-NoProfile", "-NonInteractive"]
    if len(encoded) <= 3000:
        cmd += ["-EncodedCommand", encoded]
    else:
        host_check()
        name = hashlib.sha256(script.encode()).hexdigest()[:16] + ".ps1"
        path = TMP / "scripts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(script, encoding="utf-8-sig")
        cmd += ["-ExecutionPolicy", "Bypass", "-File", UNC + "\\ansystmp\\scripts\\" + name]
    # Parallels guest execution occasionally fails when two host requests open
    # sessions simultaneously. Serialize our monitor/launcher/report requests.
    with open('/tmp/iris_prlctl.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"Guest exit {result.returncode}: {result.stdout}\n{result.stderr}")
    return result.stdout.strip().lstrip("\ufeff")

def disks(reserve=0):
    host = host_check(reserve)
    script = r"$ProgressPreference='SilentlyContinue';$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\";[int64]$d.FreeSpace"
    script = script.replace('\\"', '"')
    # Only this read-only space query is retried. Never blindly retry a launch
    # after an ambiguous guest return code, which could duplicate a solver.
    for attempt in range(3):
        try:
            win = int(guest(script))
            break
        except (RuntimeError, ValueError, subprocess.TimeoutExpired):
            if attempt == 2:
                raise
            time.sleep(.5)
    if win < WINDOWS_FLOOR:
        raise StorageLimitError(f"STOP: Windows C: free bytes {win} below {WINDOWS_FLOOR}")
    return dict(checked_utc=utc(), checked_epoch=time.time(), guest_checked_epoch=time.time(), mac_free_bytes=host,
                windows_free_bytes=win, mac_floor_bytes=MAC_FLOOR,
                windows_floor_bytes=WINDOWS_FLOOR, allowed=True)

def stop_runs(reason):
    """Only minimal stop markers are written once a storage problem is found."""
    atomic(TMP / "STOP_WORK.json", dict(time_utc=utc(), reason=reason))
    registry = TMP / "active_runs.json"
    active = json.loads(registry.read_text()) if registry.exists() else []
    for entry in active:
        runtime = (ROOT / entry["relative_runtime"]).resolve()
        if not runtime.is_relative_to(TMP.resolve()):
            continue
        (runtime / "PAUSE_REQUESTED").write_text(reason + "\n")
        # MAPDL checks this at a nonlinear equilibrium iteration. Any interrupted
        # result must be reconciled with the last accepted controller checkpoint.
        (runtime / (entry.get("job", "file") + ".abt")).write_text("nonlinear\n")

def watch():
    last_guest = 0.0
    status = None
    while True:
        try:
            free = host_check()
            if time.time() - last_guest >= 30 or status is None:
                status = disks()
                last_guest = time.time()
            status.update(checked_epoch=time.time(), checked_utc=utc(), mac_free_bytes=free)
            atomic(TMP / "host_storage_status.json", status)
        except StorageLimitError as exc:
            stop_runs(str(exc))
            print(str(exc), flush=True)
            return 2
        except Exception as exc:
            # A guest communication fault is not evidence that a disk crossed
            # its limit. Preserve the last verified time; stale data stops the
            # next coupling step. Retry communications without restarting jobs.
            atomic(TMP / 'guest_probe_error.json', dict(utc=utc(),reason=str(exc)))
            if (TMP/'STOP_WORK.json').exists():
                return 2
        time.sleep(5)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["check", "watch", "map"])
    args = parser.parse_args()
    if args.action == "watch":
        raise SystemExit(watch())
    status = disks()
    atomic(TMP / "host_storage_status.json", status)
    if args.action == "map":
        # I: is owned by this study; refuse an unrelated existing mapping.
        script = "$ErrorActionPreference='Stop';$target='" + UNC + "';"
        script += r"$d=Get-PSDrive -Name I -ErrorAction SilentlyContinue;if($d){if($d.DisplayRoot -ne $target -and $d.Root -ne $target){throw 'I: already has another mapping'}}else{& net.exe use 'I:' $target '/persistent:no';if($LASTEXITCODE -ne 0){throw 'Mapping failed'}};Get-Item -LiteralPath 'I:\model\ops.py'|Select-Object FullName,Length|ConvertTo-Json"
        print(guest(script))
    print(json.dumps(status, indent=2))

if __name__ == "__main__":
    main()

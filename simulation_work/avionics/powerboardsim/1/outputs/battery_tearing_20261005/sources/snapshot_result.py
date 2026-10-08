"""Copy a running case for read-only POST1; never launch or alter a solve.

An unstable copy is retained as rejected evidence. Use a fresh destination
after inspecting any failure; this utility never retries or overwrites one.
"""
from pathlib import Path
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys

S = Path(__file__).resolve().parent.parent
source, destination = sys.argv[1:3]
assert all(re.fullmatch(r"[a-z0-9_]+", v) for v in (source, destination))
assert source != destination
src, dst = (S / "runtime" / v for v in (source, destination))
assert not dst.exists(), "Snapshot destination already exists; inspect it"
assert not (src / "SNAPSHOT_INTENT.json").exists()
assert not (src / "REJECTED_LOAD_HISTORY.json").exists()
manifest = json.loads((src / "input_sha256.json").read_text())
for name, digest in manifest.items():
    assert hashlib.sha256((src / name).read_bytes()).hexdigest() == digest, name
assert json.loads((src / "config.json").read_text())["load_protocol"] == "continuous_solu_v2"
dst.mkdir()
for name in list(manifest) + ["input_sha256.json"]:
    shutil.copy2(src / name, dst / name)
(dst / "SNAPSHOT_INTENT.json").write_text(json.dumps({
    "source_case": source,
    "snapshot_case": destination,
    "created": datetime.datetime.now().astimezone().isoformat(),
    "purpose": "Read-only stable result copy while source continues; never launch SOLVE.",
}, indent=2) + "\n")
win_dst = "Z:" + str(dst).removeprefix("/Users/mdn").replace("/", "\\")
ps = rf"""
$ErrorActionPreference='Stop'
$src='C:\Temp\PBTear26_{source}'
$dst='C:\Temp\PBTear26_{destination}'
if(Test-Path $dst){{throw 'Native snapshot destination already exists'}}
if(-not (Test-Path "$src\tear.lock")){{throw 'Source not running: inspect completion and use normal postprocessing'}}
New-Item -ItemType Directory -Path $dst -ErrorAction Stop | Out-Null
$before=Get-Item "$src\tear.rst"
$bytes=$before.Length
$ticks=$before.LastWriteTimeUtc.Ticks
$modelHash=(Get-FileHash "$src\model.db").Hash
Copy-Item "$src\tear.rst","$src\model.db" $dst
$after=Get-Item "$src\tear.rst"
$copy=Get-Item "$dst\tear.rst"
$copiedModelHash=(Get-FileHash "$dst\model.db").Hash
$stable=($bytes -eq $after.Length -and $ticks -eq $after.LastWriteTimeUtc.Ticks -and $bytes -eq $copy.Length -and $modelHash -eq $copiedModelHash)
Copy-Item "$src\run.out","$src\tear.err","$src\solve_progress.csv" $dst
$record=@{{source=$src;destination=$dst;utc=(Get-Date).ToUniversalTime().ToString('o');rst_length_before=$bytes;rst_length_after=$after.Length;rst_length_copy=$copy.Length;rst_ticks_before=$ticks;rst_ticks_after=$after.LastWriteTimeUtc.Ticks;model_sha256=$copiedModelHash.ToLower();stable_during_copy=$stable;source_solver_active=(Test-Path "$src\tear.lock")}}
$record | ConvertTo-Json | Set-Content "$dst\NATIVE_SNAPSHOT.json" -Encoding UTF8
Copy-Item "$dst\NATIVE_SNAPSHOT.json" '{win_dst}'
if(-not $stable){{throw 'Snapshot changed during copy; evidence preserved, do not postprocess'}}
$record | ConvertTo-Json
"""
# Keep the Parallels invocation short; preserve the exact copy program beside
# its snapshot instead of sending a long UTF-16/base64 command line.
(dst / "snapshot_copy.ps1").write_text(ps)
invoke = rf"& ([scriptblock]::Create((Get-Content '{win_dst}\snapshot_copy.ps1' -Raw)))"
result = subprocess.run([sys.executable, str(S / "sources" / "vm_ps.py")],
                        input=invoke, text=True, capture_output=True, timeout=55)
print(result.stdout)
if result.returncode:
    (dst / "SNAPSHOT_COPY_FAILED.txt").write_text(result.stdout + result.stderr)
    raise RuntimeError(result.stderr)
record = json.loads((dst / "NATIVE_SNAPSHOT.json").read_text(encoding="utf-8-sig"))
assert record["stable_during_copy"]
print("Stable read-only snapshot prepared. Run native.py DESTINATION post separately.")

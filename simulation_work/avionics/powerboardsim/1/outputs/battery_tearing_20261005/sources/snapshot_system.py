"""One-shot stable read-only snapshot without mapped drives or source writes."""
from pathlib import Path
import base64
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys

S = Path(__file__).resolve().parent.parent
source, destination = sys.argv[1:3]
assert all(re.fullmatch(r'[a-z0-9_]+', v) for v in (source, destination))
assert source != destination
src, dst = (S / 'runtime' / v for v in (source, destination))
assert not dst.exists(), 'Never overwrite a snapshot'
assert not (src / 'SNAPSHOT_INTENT.json').exists()
assert not (src / 'REJECTED_LOAD_HISTORY.json').exists()
manifest = json.loads((src / 'input_sha256.json').read_text())
for name, digest in manifest.items():
    assert hashlib.sha256((src / name).read_bytes()).hexdigest() == digest, name
assert json.loads((src / 'config.json').read_text())['load_protocol'] == 'continuous_solu_v2'
assert (src / 'PREFLIGHT_PASSED.txt').read_text() == manifest['run.dat']


def ps(code):
    code = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $ErrorActionPreference='Stop'; " + code
    result = subprocess.run(['/usr/local/bin/prlctl', 'exec', 'Windows 11',
        'powershell.exe', '-NoProfile', '-EncodedCommand',
        base64.b64encode(code.encode('utf-16le')).decode()], capture_output=True,
        text=True, errors='replace', timeout=50)
    assert result.returncode == 0, (result.stdout[-2000:], result.stderr[-1000:])
    return result.stdout.strip()


dst.mkdir()
for name in list(manifest) + ['input_sha256.json', 'PREFLIGHT_PASSED.txt']:
    shutil.copy2(src / name, dst / name)
(dst / 'SNAPSHOT_INTENT.json').write_text(json.dumps({
    'source_case': source, 'snapshot_case': destination,
    'created': datetime.datetime.now().astimezone().isoformat(),
    'purpose': 'Stable read-only copy for independent POST1 while source continues; never SOLVE.',
    'transport': 'System session; exact-byte chunked copy launcher'
}, indent=2) + '\n')
script = rf"""$ErrorActionPreference='Stop'
$src='C:\Temp\PBTear26_{source}'
$dst='C:\Temp\PBTear26_{destination}'
if(Test-Path $dst){{throw 'Native snapshot exists'}}
if(-not (Test-Path "$src\tear.lock")){{throw 'Source not running; inspect completion instead'}}
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
$record=@{{source=$src;destination=$dst;utc=(Get-Date).ToUniversalTime().ToString('o');rst_length_before=$bytes;rst_length_after=$after.Length;rst_length_copy=$copy.Length;rst_ticks_before=$ticks;rst_ticks_after=$after.LastWriteTimeUtc.Ticks;rst_copy_ticks=$copy.LastWriteTimeUtc.Ticks;model_sha256=$copiedModelHash.ToLower();stable_during_copy=$stable;source_solver_active=(Test-Path "$src\tear.lock");source_input_sha256_at_verified_launch='{manifest['run.dat']}';source_input_read_note='Native input remains locked by solver; sealed local hash and prior launch verification retained, no current source input read attempted'}}
$record | ConvertTo-Json | Set-Content "$dst\NATIVE_SNAPSHOT.json" -Encoding UTF8
if(-not $stable){{throw 'Unstable copy; preserve evidence and do not postprocess'}}
$record | ConvertTo-Json
"""
target = r'C:\Temp\PBTear26_' + destination + '_copy.ps1'
(dst / 'snapshot_copy.ps1').write_text(script)
try:
    ps("if((Test-Path '" + target + "') -or (Test-Path '" + target + ".b64')){throw 'Staging exists'}; "
       "[IO.File]::WriteAllText('" + target + ".b64','')")
    encoded = base64.b64encode(script.encode()).decode()
    for start in range(0, len(encoded), 1200):
        ps("[IO.File]::AppendAllText('" + target + ".b64','" + encoded[start:start + 1200] + "')")
    ps("[IO.File]::WriteAllBytes('" + target + "',[Convert]::FromBase64String([IO.File]::ReadAllText('" + target + ".b64'))); "
       "if((Get-FileHash '" + target + "').Hash.ToLower() -ne '" + hashlib.sha256(script.encode()).hexdigest() + "'){throw 'Launcher hash mismatch'}")
    record = json.loads(ps("& ([scriptblock]::Create((Get-Content '" + target + "' -Raw)))"))
    assert record['stable_during_copy']
    assert record['rst_length_before'] == record['rst_length_after'] == record['rst_length_copy']
    assert record['rst_ticks_before'] == record['rst_ticks_after']
    # Preserve exact native JSON bytes for subsequent launch checks.
    raw = base64.b64decode(ps("[Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\\Temp\\PBTear26_" + destination + "\\NATIVE_SNAPSHOT.json'))"), validate=True)
    assert json.loads(raw.decode('utf-8-sig')) == record
    (dst / 'NATIVE_SNAPSHOT.json').write_bytes(raw)
    print(json.dumps(record, indent=2))
except Exception as error:
    (dst / 'SNAPSHOT_COPY_FAILED.txt').write_text(repr(error) + '\nInspect processes and guest files before any fresh attempt. No automatic retry.\n')
    raise

"""One-shot read-only native POST1 through the Parallels system session.

No mapped drives, structural SOLVE, automatic retries, or input changes.
Actions: prepare (host only), start (after native solve ends), check.
"""
from pathlib import Path
import base64
import datetime
import hashlib
import json
import re
import subprocess
import sys

S = Path(__file__).resolve().parent.parent
case, action = sys.argv[1:3]
assert re.fullmatch(r'[a-z0-9_]+', case)
assert action in ('prepare', 'start', 'check')
D = S / 'runtime' / case
rt = 'C:\\Temp\\PBTear26_' + case
exe = r'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_new(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def now():
    return datetime.datetime.now().astimezone().isoformat()


def ps(code):
    code = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $ErrorActionPreference='Stop'; " + code
    result = subprocess.run(
        ['/usr/local/bin/prlctl', 'exec', 'Windows 11', 'powershell.exe',
         '-NoProfile', '-EncodedCommand', base64.b64encode(code.encode('utf-16le')).decode()],
        capture_output=True, text=True, errors='replace', timeout=50)
    if result.returncode:
        raise RuntimeError((result.returncode, result.stdout[-2000:], result.stderr[-1000:]))
    return result.stdout.strip()


manifest = json.loads((D / 'input_sha256.json').read_text())
for name, digest in manifest.items():
    assert sha((D / name).read_bytes()) == digest, name
cfg = json.loads((D / 'config.json').read_text())
assert cfg.get('load_protocol') == 'continuous_solu_v2'
assert not (D / 'REJECTED_LOAD_HISTORY.json').exists()
assert (D / 'PREFLIGHT_PASSED.txt').read_text() == manifest['run.dat']
post = (D / 'post.dat').read_bytes()
snapshot = None
if (D / 'SNAPSHOT_INTENT.json').exists():
    assert not (D / 'SNAPSHOT_COPY_FAILED.txt').exists()
    snapshot = json.loads((D / 'NATIVE_SNAPSHOT.json').read_text(encoding='utf-8-sig'))
    assert snapshot['stable_during_copy']
    assert snapshot['rst_length_before'] == snapshot['rst_length_after'] == snapshot['rst_length_copy']
    assert snapshot['rst_ticks_before'] == snapshot['rst_ticks_after']
assert re.search(rb'^/POST1\s*$', post, re.M)
assert not re.search(rb'^\s*(?:SOLVE|/SOLU)(?:\s|,|$)', post, re.M | re.I)
assert re.search(rb'^\s*\*IF,SS,EQ,999999,THEN\s*\n\s*\*CYCLE', post, re.M)

launcher = S / 'audit' / (case + '_post_system_launcher.ps1')
target = rt + r'\post_system_launcher.ps1'
guard = """$d='%s'
if((Test-Path "$d\\tear.lock") -or (Test-Path "$d\\post.lock")){throw 'Runtime still active'}
if((Test-Path "$d\\post.out") -or (Test-Path "$d\\post.dat")){throw 'Post files exist; inspect before any retry'}
if(-not (Test-Path "$d\\tear.rst")){throw 'Result file absent'}
if(-not (Test-Path "$d\\model.db")){throw 'Database absent'}
$l=& 'C:\\Program Files\\ANSYS Inc\\v261\\licensingclient\\winx64\\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25
if(($l -join "`n") -notmatch 'Total of 0 licenses? in use'){throw 'PrepPost unavailable'}
""" % rt
if snapshot is None:
    guard += """if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'A native solver is active; inspect first'}
if((Get-FileHash "$d\\run.dat").Hash.ToLower() -ne '%s'){throw 'Native input hash changed'}
if((Get-Content "$d\\run.out" -Tail 100 | Out-String) -notmatch 'NUMBER OF ERROR\\s+MESSAGES ENCOUNTERED='){throw 'Native completion footer absent'}
""" % manifest['run.dat']
else:
    assert snapshot['source_input_sha256_at_verified_launch'] == manifest['run.dat']
    guard += """if((Get-FileHash "$d\\NATIVE_SNAPSHOT.json").Hash.ToLower() -ne '%s'){throw 'Snapshot record changed'}
$rst=Get-Item "$d\\tear.rst"
if($rst.Length -ne %d -or $rst.LastWriteTimeUtc.Ticks -ne %d){throw 'Snapshot result changed'}
if((Get-FileHash "$d\\model.db").Hash.ToLower() -ne '%s'){throw 'Snapshot database changed'}
""" % (sha((D / 'NATIVE_SNAPSHOT.json').read_bytes()), snapshot['rst_length_copy'],
           snapshot['rst_copy_ticks'], snapshot['model_sha256'])
script = "$ErrorActionPreference='Stop'\n" + guard + """
[IO.File]::WriteAllBytes("$d\\post.dat",[Convert]::FromBase64String('%s'))
if((Get-FileHash "$d\\post.dat").Hash.ToLower() -ne '%s'){throw 'Post hash mismatch'}
$p=Start-Process '%s' -ArgumentList '-b nolist -s noread -smp -np 1 -p preppost -j post -i post.dat -o post.out' -WorkingDirectory $d -PassThru
$p.Id
""" % (base64.b64encode(post).decode(), manifest['post.dat'], exe)

if action == 'prepare':
    if launcher.exists():
        assert launcher.read_bytes() == script.encode(), 'Preserve existing differing launcher'
    else:
        launcher.write_bytes(script.encode())
    print('Prepared host-only read-only launcher:', launcher, sha(script.encode()))
elif action == 'start':
    assert launcher.read_bytes() == script.encode()
    assert snapshot is not None or (D / 'SOLVE_STARTED.json').exists()
    assert not (D / 'POST_STARTED.json').exists()
    assert not (D / 'POST_SYSTEM_INTENT.json').exists(), 'Inspect previous attempt; no automatic retry'
    # Guard is checked before transfer and again immediately before launching.
    ps(guard)
    intent = {'time': now(), 'post_sha256': manifest['post.dat'],
              'launcher_sha256': sha(script.encode()), 'transport': 'Parallels system session'}
    save_new(D / 'POST_SYSTEM_INTENT.json', intent)
    try:
        ps("if((Test-Path '" + target + "') -or (Test-Path '" + target + ".b64')){throw 'Staged launcher exists'}; "
           "[IO.File]::WriteAllText('" + target + ".b64','')")
        encoded = base64.b64encode(script.encode()).decode()
        for start in range(0, len(encoded), 1200):
            ps("[IO.File]::AppendAllText('" + target + ".b64','" + encoded[start:start + 1200] + "')")
        ps("[IO.File]::WriteAllBytes('" + target + "',[Convert]::FromBase64String([IO.File]::ReadAllText('" + target + ".b64'))); "
           "if((Get-FileHash '" + target + "').Hash.ToLower() -ne '" + sha(script.encode()) + "'){throw 'Launcher hash mismatch'}")
        pid = ps("& ([scriptblock]::Create((Get-Content '" + target + "' -Raw)))")
        assert re.fullmatch(r'\d+', pid), pid
        save_new(D / 'POST_STARTED.json', dict(intent, pid=pid))
        print('Read-only native POST1 launched:', pid)
    except Exception as error:
        save_new(D / 'POST_SYSTEM_TRANSPORT_FAILURE.json', {'time': now(), 'error': repr(error),
                 'action': 'Inspect guest processes, locks and files before any manual recovery; do not rerun.'})
        raise
else:
    started = json.loads((D / 'POST_STARTED.json').read_text())
    assert not (D / 'POST_PASSED.json').exists()
    ps("if(Test-Path '" + rt + "\\post.lock'){throw 'Postprocessing active'}; "
       "if(Get-Process -Id " + str(int(started['pid'])) + " -ErrorAction SilentlyContinue){throw 'Launcher still active'}")
    for name in ('post.out', 'post.err'):
        raw = base64.b64decode(ps("[Convert]::ToBase64String([IO.File]::ReadAllBytes('" + rt + "\\" + name + "'))"), validate=True)
        dest = D / name
        if dest.exists():
            assert dest.read_bytes() == raw, 'Preserve different local output: ' + name
        else:
            dest.write_bytes(raw)
    out = (D / 'post.out').read_text(errors='replace')
    counts = re.findall(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)', out)
    assert counts and counts[-1] == '0', 'Native POST1 did not complete with zero errors'
    save_new(D / 'POST_PASSED.json', {'time': now(), 'post_sha256': manifest['post.dat'],
             'out_sha256': sha((D / 'post.out').read_bytes())})
    print('Native converged-only extraction completed without errors; physical acceptance still required.')

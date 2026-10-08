"""Transfer the preserved read-only post launcher after transport failure."""
from pathlib import Path
import subprocess, base64, hashlib, json, datetime

S = Path(__file__).resolve().parent.parent
D = S / 'runtime/cont_force5em5'
F = S / 'audit/cont_force5em5_post_system_launcher.ps1'
TARGET = r'C:\Temp\PBTear26_cont_force5em5\post_system_launcher.ps1'

def ps(code):
    result = subprocess.run(
        ['/usr/local/bin/prlctl', 'exec', 'Windows 11', 'powershell.exe', '-NoProfile', '-Command', code],
        capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    return result.stdout.strip()

assert not (D / 'POST_STARTED.json').exists()
(S / 'audit/cont_force5em5_post_transport_failure.json').write_text(json.dumps({
    'time': datetime.datetime.now().astimezone().isoformat(),
    'error': 'PrlJob_GetResult Invalid argument on long direct command',
    'verified_after': 'No ANSYS processes or post.dat/post.out/post.lock; no launch occurred',
    'recovery': 'Transfer preserved launcher in small base64 chunks, verify SHA256, then short invocation'
}, indent=2) + '\n')
payload = F.read_bytes()
ps("$ErrorActionPreference='Stop'; if(Test-Path '" + TARGET + "'){throw 'Launcher exists'}; "
   "if(Test-Path '" + TARGET + ".b64'){throw 'Staging exists'}; [IO.File]::WriteAllText('" + TARGET + ".b64','')")
encoded = base64.b64encode(payload).decode()
for start in range(0, len(encoded), 1200):
    ps("[IO.File]::AppendAllText('" + TARGET + ".b64','" + encoded[start:start+1200] + "')")
digest = hashlib.sha256(payload).hexdigest()
ps("$ErrorActionPreference='Stop'; [IO.File]::WriteAllBytes('" + TARGET + "',"
   "[Convert]::FromBase64String([IO.File]::ReadAllText('" + TARGET + ".b64'))); "
   "if((Get-FileHash '" + TARGET + "').Hash.ToLower() -ne '" + digest + "'){throw 'Launcher hash mismatch'}")
pid = ps("& ([scriptblock]::Create((Get-Content '" + TARGET + "' -Raw)))")
manifest = json.loads((D / 'input_sha256.json').read_text())
(D / 'POST_STARTED.json').write_text(json.dumps({
    'pid': pid, 'time': datetime.datetime.now().astimezone().isoformat(),
    'transport': 'System session; byte-exact chunked launcher transfer; no SOLVE; sealed post.dat unchanged',
    'post_sha256': manifest['post.dat'], 'launcher_sha256': digest
}, indent=2) + '\n')
print('Read-only native postprocessing launched:', pid)

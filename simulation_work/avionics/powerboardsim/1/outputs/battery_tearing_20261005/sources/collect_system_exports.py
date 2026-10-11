"""Collect completed native post exports without the user's mapped Z: drive."""
from pathlib import Path
import base64, subprocess, hashlib, json, sys, re, zipfile, datetime

S = Path(__file__).resolve().parent.parent
case = sys.argv[1]
assert re.fullmatch(r'[a-z0-9_]+', case)
D = S / 'runtime' / case
assert (D / 'POST_PASSED.json').exists()
rt = 'C:\\Temp\\PBTear26_' + case

def ps(command, timeout=50):
    command = '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; ' + command
    r = subprocess.run(['/usr/local/bin/prlctl', 'exec', 'Windows 11',
                        'powershell.exe', '-NoProfile', '-EncodedCommand',
                        base64.b64encode(command.encode('utf-16le')).decode()],
                       capture_output=True, text=True, errors='replace', timeout=timeout)
    assert r.returncode == 0, (r.stdout[-1000:], r.stderr[-1000:])
    return r.stdout.strip()

archive = rt + r'\post_exports.zip'
command = """$ErrorActionPreference='Stop'; $d='%s';
if((Test-Path "$d\\tear.lock") -or (Test-Path "$d\\post.lock")){throw 'Runtime active'};
if(Test-Path '%s'){throw 'Archive exists; inspect before repeating'};
$files=Get-ChildItem $d -File | Where-Object {$_.Extension -in '.csv','.out','.err','.txt','.db','.log','.ldhi','.mntr','.stat'};
$manifest=@($files | ForEach-Object {[PSCustomObject]@{name=$_.Name;length=$_.Length;sha256=(Get-FileHash $_.FullName).Hash.ToLower()}});
$manifest | ConvertTo-Json | Set-Content "$d\\post_exports_manifest.json" -Encoding UTF8;
$paths=@($files.FullName)+@("$d\\post_exports_manifest.json");
Compress-Archive -Path $paths -DestinationPath '%s';
(Get-FileHash '%s').Hash.ToLower()
""" % (rt, archive, archive, archive)
(S / 'audit' / (case + '_export_archive_command.ps1')).write_text(command)
digest = ps(command, timeout=300).splitlines()[-1].strip()
assert re.fullmatch(r'[a-f0-9]{64}', digest), digest
print('Native export archive complete; transferring.', flush=True)
payload = base64.b64decode(ps("[Convert]::ToBase64String([IO.File]::ReadAllBytes('" + archive + "'))", timeout=300), validate=True)
assert hashlib.sha256(payload).hexdigest() == digest
dest = D / 'post_exports.zip'
assert not dest.exists()
dest.write_bytes(payload)
with zipfile.ZipFile(dest) as z:
    assert z.testzip() is None
    manifest = json.loads(z.read('post_exports_manifest.json').decode('utf-8-sig'))
    for item in manifest:
        name = item['name']
        assert Path(name).name == name
        content = z.read(name)
        assert len(content) == item['length']
        assert hashlib.sha256(content).hexdigest() == item['sha256']
        existing = D / name
        if existing.exists():
            assert existing.read_bytes() == content, 'Existing export differs: ' + name
        else:
            existing.write_bytes(content)
    (D / 'post_exports_manifest.json').write_bytes(z.read('post_exports_manifest.json'))
(D / 'EXPORT_COLLECTION_VERIFIED.json').write_text(json.dumps({
    'time': datetime.datetime.now().astimezone().isoformat(), 'archive_sha256': digest,
    'files': len(manifest), 'archive_bytes': len(payload),
    'native_binary_results': 'Full RST/restart files preserved in original guest directory; not included in this export archive.'
}, indent=2) + '\n')
print('Collected and hash-verified', len(manifest), 'files;', len(payload), 'archive bytes.')

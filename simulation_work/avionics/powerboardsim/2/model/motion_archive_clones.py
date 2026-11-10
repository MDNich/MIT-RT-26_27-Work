"""Seed a fresh transient archive with separately verified clones of unchanged modal parent files."""
import json
import re
import subprocess
import sys

from audit_local import ROOT,read
from archive_shared import clone_file
from film_identity import digest,verified,write_json

FILES=('file.mode','file.full')


def copy_matching(parent,destination,parent_hashes,guest_hashes):
    """Leave changed guest files for the normal archiver and preserve every existing file."""
    rows=[]
    for name in FILES:
        sha=parent_hashes[name]
        if guest_hashes.get(name)!=sha:
            continue
        source=parent/name
        target=destination/name
        if target.exists():
            continue
        verified(source,sha)
        destination.mkdir(parents=True,exist_ok=True)
        clone_file(source,target)
        assert target.stat().st_ino!=source.stat().st_ino and digest(target)==sha
        rows.append(dict(name=name,sha256=sha,bytes=target.stat().st_size))
    return rows


def prefill(case,campaign,state,receipt):
    match=re.fullmatch(r'(snug125_(?:nylon|aluminium))_motion_[XYZ]',case)
    if not match:return
    assert re.fullmatch('[A-Za-z0-9_]+',campaign)
    parent=match[1]+'_enforced'
    assert state['parent']==parent and state['case']==case and state['exit']==0 and state['phase']=='solver_complete'
    guest=rf'C:\Temp\PBCaseStudy\{campaign}\{case}'
    assert state['work'].lower()==guest.lower() and state['motion_kind']=='transient'
    note=receipt/'modal_archive_clones.json'
    if note.is_file() or (receipt/'archive.lock').exists() or list(receipt.glob('archive_*request*.json')):
        return
    archive=ROOT/'.runtime/archive'/campaign
    parent_proof=read(ROOT/'validation/motion'/(parent+'.json'))
    assert parent_proof['case']==parent and parent_proof['campaign']==campaign
    ledger=read(ROOT/'.runtime/receipts'/campaign/parent/'archived.json')
    hashes={x['name']:x['sha256'] for x in ledger['files']}
    assert all(hashes[name]==parent_proof['smp_parent_sha256'][name] for name in FILES)
    # The guest archiver independently hashes the native files and each destination again before release.
    ps=("$ErrorActionPreference='Stop'; $h=@{};"
        f"$d='{guest}'; foreach($n in 'file.mode','file.full') {{"
        "$h[$n]=(Get-FileHash -LiteralPath (Join-Path $d $n)).Hash.ToLower()};"
        "$h|ConvertTo-Json -Compress")
    query=subprocess.run([sys.executable,str(ROOT/'model/guest_command.py'),'--timeout','90'],
                         input=ps,text=True,capture_output=True)
    if query.returncode:
        return
    guest_hashes=json.loads(query.stdout.lstrip('\ufeff'))
    if set(guest_hashes)!=set(FILES) or not all(re.fullmatch('[a-f0-9]{64}',v) for v in guest_hashes.values()):
        raise ValueError('Invalid closed guest motion hashes')
    rows=copy_matching(archive/parent,archive/case,hashes,guest_hashes)
    write_json(note,dict(case=case,parent=parent,campaign=campaign,guest_hashes=guest_hashes,
                         independently_cloned_files=rows))

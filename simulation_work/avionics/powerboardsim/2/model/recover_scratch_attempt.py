"""Retire closed storage-stop attempts while the serial supervisor is offline; preserve both receipts and inputs."""
import argparse
import fcntl
import json
import re
import subprocess
import sys

from audit_local import ROOT,read
from film_identity import digest,verified,write_json


def recover(campaign,cases):
    if not re.fullmatch('[A-Za-z0-9_]+',campaign):raise ValueError(campaign)
    rt=ROOT/'.runtime'
    lock=(rt/'global_queue.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    checked=read(ROOT/'validation/shared_dmp_control.json')
    assert checked['ranks']==12 and checked['maximum_relative_frequency_error']<.002
    target=ROOT/'validation/storage_recovery.json'
    history=read(target) if target.is_file() else {}
    for case in cases:
        if not re.fullmatch('[A-Za-z0-9_]+',case):raise ValueError(case)
        if case in history:
            assert history[case]['campaign']==campaign
            continue
        live=rt/'receipts'/campaign/case
        saved=rt/'stopped_receipts'/campaign/case
        if saved.exists() and live.exists():raise RuntimeError('Existing successor needs review')
        evidence=saved if saved.exists() else live
        assert (evidence/'stopped_released.txt').is_file()
        state=read(evidence/'status.json');ledger=read(evidence/'stopped_archived.json')
        assert state['phase']=='failed' and state['case']==ledger['case']==case and ledger['campaign']==campaign
        assert 'reserve' in state['failure'] or 'Insufficient space for a fresh' in state['failure']
        files=rt/'stopped_archive'/campaign/case
        for entry in ledger['files']:
            name=entry['name']
            assert (files/name).parent==files and (files/name).stat().st_size==entry['bytes']
            verified(files/name,entry['sha256'])
        assert digest(files/'model.inp')==state['input_sha256'].lower()
        base=r'C:\Temp\PBCaseStudy'+'\\'+campaign
        assert state['work']==base+'\\'+case
        dst=base+'\\closed_storage_attempts\\'+case
        # A lost acknowledgement is recoverable by checking both original and retired paths.
        ps=f"""
$ErrorActionPreference='Stop'
$active=@(Get-CimInstance Win32_Process|Where-Object {{$_.Name -match '^(ANSYS(261)?|mapdl|mpiexec|hydra_pmi_proxy)\\.exe$' -or ($_.Name -eq 'powershell.exe' -and $_.CommandLine -like '*\\native_run.ps1 -Case *')}})
if ($active.Count){{throw 'A native solver or launcher is active'}}
$a='{state["work"]}';$b='{dst}'
if ((Test-Path $a) -eq (Test-Path $b)){{throw 'Ambiguous old and retired directories'}}
if (Test-Path $a){{
 $rest=@(Get-ChildItem -LiteralPath $a -File|Where-Object Length -gt 5000000)
 if ($rest.Count){{throw 'Some large guest files have not been verified and released'}}
 New-Item -ItemType Directory -Path (Split-Path $b) -Force|Out-Null
 Move-Item -LiteralPath $a -Destination $b
}}
if (!(Test-Path $b) -or (Test-Path $a)){{throw 'Retirement not confirmed'}}
'RETIRED_CLOSED_ATTEMPT'
"""
        reply=subprocess.run([sys.executable,str(ROOT/'model/guest_command.py')],input=ps,text=True,capture_output=True)
        if reply.returncode or reply.stdout.strip()!='RETIRED_CLOSED_ATTEMPT':raise RuntimeError(reply.stdout+reply.stderr)
        if live.exists():
            saved.parent.mkdir(parents=True,exist_ok=True);live.rename(saved)
        history[case]=dict(campaign=campaign,stopped_reason=state['failure'],original_guest_start=state['utc'],
            sealed_input_sha256=state['input_sha256'].lower(),original_manifest_sha256=digest(saved/'stopped_archived.json'),
            checked_files=len(ledger['files']),checked_bytes=sum(f['bytes'] for f in ledger['files']),
            guest_evidence_directory=dst,closed_solver_listing_sha256=digest(files/'solve.out') if (files/'solve.out').is_file() else None)
        write_json(target,history)
        print(case,history[case]['checked_bytes'],'verified',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign');parser.add_argument('cases',nargs='+')
    args=parser.parse_args();recover(args.campaign,args.cases)

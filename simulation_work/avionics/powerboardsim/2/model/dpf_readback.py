"""Export only accepted archived files or completed solver archives for readback. No MAPDL invocation."""
import argparse
import fcntl
import json
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
from film_identity import ROOT,verified,write_json


def read_with_recovery(out,spec,command,guest_out):
    sets=spec['sets']
    def complete():
        return all((out/f'set_{k:04d}.json').is_file() for k in sets)
    def guest(script,timeout):
        return subprocess.run([sys.executable,str(ROOT/'model/guest_command.py'),'--timeout',str(timeout)],
                              input=script,text=True,capture_output=True)
    for attempt in range(3):
        if complete():return
        if (out/'dispatch.json').exists():
            if json.loads((out/'dispatch.json').read_text())!=spec:raise ValueError('Changed DPF request')
            log=out/'export.log'
            if log.is_file():
                output=log.read_text()
                if output.strip() and not any(t in output for t in ('PrlJob_','TimeoutExpired','timed out')):
                    raise RuntimeError('DPF readback failed: '+output[-1500:])
            absent=0;unknown_since=None
            while absent<2:
                if complete():return
                time.sleep(5)
                check=guest("$p=@(Get-CimInstance Win32_Process -ErrorAction Stop|Where-Object {"
                     "$_.Name -match '^ipy(64)?\\.exe$' -and $_.CommandLine -like '*"+guest_out+"*'});[string]$p.Count",30)
                value=check.stdout.lstrip('\ufeff').strip()
                if check.returncode or not value.isdecimal():
                    absent=0
                    if unknown_since is None:unknown_since=time.monotonic()
                    if time.monotonic()-unknown_since>120:
                        raise RuntimeError('Guest DPF process status is uncertain; existing attempt preserved')
                    continue
                unknown_since=None
                absent=absent+1 if int(value)==0 else 0
            if complete():return
            n=1
            while (out/f'transport_attempt_{n}').exists():n+=1
            if n>=3:raise RuntimeError('Three DPF transport attempts need inspection')
            old=out/f'transport_attempt_{n}';old.mkdir()
            for k in sets:
                if not (out/f'set_{k:04d}.json').exists():
                    for file in out.glob(f'set_{k:04d}.*'):file.rename(old/file.name)
            (out/'dispatch.json').rename(old/'dispatch.json')
            if log.exists():log.rename(old/'export.log')
        write_json(out/'dispatch.json',spec)
        result=guest(command,3600)
        (out/'export.log').write_text(result.stdout+result.stderr)
        if complete():return
    raise RuntimeError('Incomplete DPF readback after transport recovery')


def export(case,campaign,sets,job='file'):
    relative=Path('.runtime/archive')/campaign/case/(job+'.rst')
    path=ROOT/relative
    ledger=json.loads((ROOT/'.runtime/receipts'/campaign/case/'archived.json').read_text(encoding='utf-8-sig'))
    assert case==ledger['case'] and campaign==ledger['campaign']
    sha=next(r['sha256'] for r in ledger['files'] if r['name']==path.name);verified(path,sha)
    # A set request has a unique immutable identity and isolated output directory.
    sets=sorted(set(sets));assert sets and sets[0]>0
    key='_'.join(map(str,sets))
    out=ROOT/'.runtime/post'/campaign/case/'dpf_u'/('sets_'+key);out.mkdir(parents=True,exist_ok=True)
    lock=(out/'request.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    spec=dict(case=case,campaign=campaign,source_sha256=sha,sets=sets)
    if (out/'request.json').exists():assert json.loads((out/'request.json').read_text())==spec
    else:write_json(out/'request.json',spec)
    def windows(p):
        return str(Path(r'\\Mac\Home').joinpath(*p.relative_to(Path('/Users/mdn')).parts)).replace('/','\\')
    if not all((out/f'set_{i:04d}.json').exists() for i in sets):
        ps="& 'C:\\Program Files\\ANSYS Inc\\v261\\commonfiles\\IronPython\\ipy64.exe' '{}' '{}' '{}'\nexit $LASTEXITCODE".format(
            windows(ROOT/'model/dpf_export_u.py'),windows(path),windows(out))
        read_with_recovery(out,spec,ps,windows(out))
    for k in sets:
        stem=out/f'set_{k:04d}'
        m=json.loads(stem.with_suffix('.json').read_text())
        ids=np.fromfile(stem.with_suffix('.ids'),'<i4');u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
        assert m['set']==k and m['components']==3 and m['source_sha256']==sha and m['unit'].lower()=='m' and len(ids)==len(u)==m['nodes'] and len(np.unique(ids))==len(ids)
        assert np.all(np.isfinite(u))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('case');p.add_argument('campaign');p.add_argument('sets',type=int,nargs='+')
    a=p.parse_args();print(export(a.case,a.campaign,a.sets))

"""Export only accepted archived files or completed solver archives for readback. No MAPDL invocation."""
import argparse
import fcntl
import json
import subprocess
import sys
from pathlib import Path
import numpy as np
from film_identity import ROOT,verified,write_json


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
    lock=(out/'request.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    spec=dict(case=case,campaign=campaign,source_sha256=sha,sets=sets)
    if (out/'request.json').exists():assert json.loads((out/'request.json').read_text())==spec
    else:write_json(out/'request.json',spec)
    def windows(p):
        return str(Path(r'\\Mac\Home').joinpath(*p.relative_to(Path('/Users/mdn')).parts)).replace('/','\\')
    if not all((out/f'set_{i:04d}.json').exists() for i in sets):
        if (out/'dispatch.json').exists():raise RuntimeError('Existing or uncertain DPF readback; inspect before retrying')
        ps="& 'C:\\Program Files\\ANSYS Inc\\v261\\commonfiles\\IronPython\\ipy64.exe' '{}' '{}' '{}'\nexit $LASTEXITCODE".format(
            windows(ROOT/'model/dpf_export_u.py'),windows(path),windows(out))
        write_json(out/'dispatch.json',spec)
        p=subprocess.run([sys.executable,str(ROOT/'model/guest_command.py')],input=ps,text=True,capture_output=True)
        (out/'export.log').write_text(p.stdout+p.stderr)
        if p.returncode or 'DPF_U_EXPORT_DONE' not in p.stdout:raise RuntimeError((p.stdout+p.stderr)[-2000:])
    for k in sets:
        stem=out/f'set_{k:04d}'
        m=json.loads(stem.with_suffix('.json').read_text())
        ids=np.fromfile(stem.with_suffix('.ids'),'<i4');u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
        assert m['source_sha256']==sha and m['unit'].lower()=='m' and len(ids)==len(u)==m['nodes'] and len(np.unique(ids))==len(ids)
        assert np.all(np.isfinite(u))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('case');p.add_argument('campaign');p.add_argument('sets',type=int,nargs='+')
    a=p.parse_args();print(export(a.case,a.campaign,a.sets))

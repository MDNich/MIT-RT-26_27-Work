"""Validate a separately preserved interrupted DMP export; apply only explicitly.

Not the POST1/EKILL exception. Requires a new user-authorized recovery, a native
re-export of the last accepted reference and the converged pending step, and a
native distributed restart setup check. Never relaxes controller thresholds.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def load(p):
    return json.loads(p.read_text())


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def module(p):
    spec = importlib.util.spec_from_file_location('recovery_coupler', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def compare(a, b):
    if a.keys() != b.keys():
        raise ValueError('Reference export ID sets differ')
    worst = 0.0
    for k, av in a.items():
        bv = b[k]
        if len(av) != len(bv):
            raise ValueError('Reference export column counts differ')
        for x, y in zip(av, bv):
            if not math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-8):
                raise ValueError(f'Reference mismatch {k}: {x} != {y}')
            worst = max(worst, abs(x-y))
    return worst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    root, evidence = args.root.resolve(), args.evidence.resolve()
    assert root != evidence and root.is_dir() and evidence.is_dir()
    assert not (root/'coupler_error.txt').exists()
    for name in ('state.json', 'pending.json', 'input_manifest.json'):
        assert sha(root/name) == sha(evidence/name), f'Changed {name}'
    for name, value in load(root/'input_manifest.json').items():
        assert sha(root/name) == value == sha(evidence/name), name
    c = module(root/'coupler.py')
    s, p, cfg, mesh = (load(root/n) for n in ('state.json','pending.json','config.json','mesh_map.json'))
    assert s['status'] == 'RUNNING' and p['index'] == s['index']+1
    assert s['config_sha256'] == c.fingerprint(cfg)
    expected_pending, _ = c.prepare_step(mesh, cfg, s)
    assert json.loads(json.dumps(expected_pending)) == p, 'Pending loads do not derive from accepted state (use original Windows CPython)'
    native = (root/'recovery_verify424.out').read_text(errors='replace')
    assert 'RECOVERY_VERIFY424_COMPLETE_NO_SOLVE' in native
    assert '*** ERROR ***' not in native
    probe = (root/'probe_restart424.out').read_text(errors='replace')
    assert 'RESTART424_RESTORE_NO_SOLVE_COMPLETE' in probe
    assert 'PREVIOUS LOADSTEP =    424 SUBSTEP =      1' in probe
    assert '*** ERROR ***' not in probe and '*** WARNING ***' not in probe
    for rank in range(cfg['ranks']):
        log = evidence/('solve_20260922_054629.out' if rank == 0 else f'file{rank}.out')
        text = log.read_text(errors='replace')
        assert 'LOAD STEP   424   SUBSTEP     1  COMPLETED' in text
        assert 'TIME =   5.48750' in text
    reference_errors = {}
    for ref, old in [('reference423_nodes.txt','node_temperatures.txt'),
                     ('reference423_element.txt','element_fields.txt'),
                     ('reference423_energy.txt','energy_fields.txt')]:
        reference_errors[ref] = compare(c.read_rows(root/ref), c.read_rows(evidence/old))
    assert abs(float((root/'reference423_time.txt').read_text())-s['time_s']) < 1e-8
    observed = float((root/'observed_time.txt').read_text())
    assert abs(observed-p['target']) < 1e-8
    restarts = {}
    for ext in ('r001','esav'):
        paths = [root/f'file{r}.{ext}' for r in range(cfg['ranks'])]
        assert all(x.is_file() and x.stat().st_size > 0 for x in paths)
        assert max(x.stat().st_mtime for x in paths)-min(x.stat().st_mtime for x in paths) <= 5
        for x in paths:
            h = sha(x)
            assert h == sha(evidence/x.name), f'Restart changed during extraction: {x.name}'
            restarts[x.name] = dict(bytes=x.stat().st_size, sha256=h)
    for name in ('file.rdb','file.ldhi'):
        assert sha(root/name) == sha(evidence/name), name
        restarts[name] = dict(bytes=(root/name).stat().st_size,sha256=sha(root/name))
    temp = {k:v[0] for k,v in c.read_rows(root/'node_temperatures.txt').items()}
    new, audit = c.accept_step(mesh,cfg,s,p,temp,c.read_rows(root/'element_fields.txt'),
                             c.read_rows(root/'energy_fields.txt'),observed)
    proof = dict(utc=datetime.now(timezone.utc).isoformat(),
                 authorization='Explicit user request to update report and restart after exit -1',
                 cause='Unexplained MAPDL exit -1 during result finalization; not a POST1 rejection',
                 archive=str(evidence), working_runtime=str(root),
                 state_before={k:s[k] for k in ('index','time_s','status','layer')},
                 recovered_index=new['index'], recovered_time_s=new['time_s'],
                 reference_export_max_abs_differences=reference_errors,
                 reference_relative_tolerance=1e-6, reference_absolute_tolerance=1e-8,
                 restart_files=restarts, audit=audit,
                 native_verification_sha256=sha(root/'recovery_verify424.out'),
                 native_restart_setup_sha256=sha(root/'probe_restart424.out'),
                 restart_scope='Setup/header validation only; successful next accepted step required to demonstrate continuation',
                 input_manifest_sha256=sha(root/'input_manifest.json'))
    print(json.dumps({k:v for k,v in proof.items() if k != 'restart_files'},indent=2))
    if not args.apply:
        return
    # All physical validation above is read-only. Publish through the unchanged
    # controller, then request its normal accepted-checkpoint pause transition.
    subprocess.run([sys.executable,'-B',str(root/'coupler.py'),'accept','--root',str(root)],check=True)
    (root/'PAUSE_REQUESTED').write_text('Explicit recovery checkpoint pause\n')
    subprocess.run([sys.executable,'-B',str(root/'coupler.py'),'prepare','--root',str(root)],check=True)
    after = load(root/'state.json')
    assert after['status'] == 'PAUSED_AT_CHECKPOINT' and after['index'] == p['index']
    proof['state_after'] = {k:after[k] for k in ('index','time_s','status','layer')}
    (root/'RECOVERY_EXIT_MINUS1_PROVENANCE.json').write_text(json.dumps(proof,indent=2)+'\n')
    stale = root/'recovery_exit_minus1_evidence'
    stale.mkdir(exist_ok=False)
    for name in ('PREFLIGHT_OK.txt','file.lock'):
        if (root/name).exists():
            shutil.move(root/name,stale/name)
    print('RECOVERED_ACCEPTED_CHECKPOINT_READY_FOR_NATIVE_PREFLIGHT')


if __name__ == '__main__':
    main()

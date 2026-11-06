"""Audit native full-wall outputs by replaying the exported free nodal fields.

Replay reconstructs the linear subproblems and checks their MAPDL solutions,
then recomputes mass, enthalpy, recession and the final event from those fields.
Synthetic reader fixtures cannot create a native acceptance receipt.
"""
import json
import math
from pathlib import Path
import re
import time
from zipfile import ZipFile

import numpy as np

from continuous_heating_campaign import digest
from ops import ROOT,atomic,disks,host_check,utc
from prepare_sector_exposures import JOBS,PACKAGE
from sector_exposure import balances,integrate
from sector_mapdl import commands,parse_field,topology
from sector_wall import banded


def load_job(job):
    manifest=json.loads((PACKAGE/'manifest.json').read_text())
    for file in ['controller.zip',job+'.json',job+'.inp',job+'_settings.json']:
        if digest(PACKAGE/file)!=manifest[file]:
            raise ValueError('Changed input '+file)
    return tuple(json.loads((PACKAGE/(job+suffix)).read_text()) for suffix in ('.json','_settings.json'))


def replay(settings,input_fields,guard):
    seq=0
    max_error=0.
    geom=settings['configuration']['geometry']
    def step(block):
        nonlocal seq,max_error
        seq+=1
        raw=input_fields(seq,block)
        real=parse_field(raw,block,geom,seq)
        error=float(np.max(abs(real-banded(block))))
        if error>2e-6: raise ValueError(f'Independent thermal block differs by {error:g} K')
        max_error=max(max_error,error)
        return real
    record=integrate(settings,step,guard)
    return record,seq,max_error


def differences(a,b):
    if isinstance(a,dict):
        if set(a)!=set(b): raise ValueError('Record keys differ')
        return max((differences(a[k],b[k]) for k in a),default=0.)
    if isinstance(a,list):
        if len(a)!=len(b): raise ValueError('Record dimensions differ')
        return max((differences(i,j) for i,j in zip(a,b)),default=0.)
    return abs(a-b)/max(1.,abs(a),abs(b))


def audit(job,run):
    expected,settings=load_job(job)
    receipt=json.loads((run/'guest_terminal.json').read_text(encoding='utf-8-sig'))
    terminal=json.loads((run/'sector_terminal.json').read_text())
    assert digest(run/(job+'.inp'))==expected['deck_sha256']==receipt['guest_input_sha256'].lower()
    assert terminal['nonce']==receipt['nonce'] and receipt['exit_code']==0 and receipt['job']==job
    assert terminal['settings']==settings and terminal['controller_sha256']==expected['controller_sha256']
    assert not (run/'sector_failure.json').exists()
    files=[job+'.out','sector_fields.zip','sector_terminal.json']
    for name in files: assert digest(run/name)==receipt['guest_sha256'][name].lower()
    output=(run/files[0]).read_text(errors='replace')
    for token in ['IRIS_WHOLE_SECTOR_RETURNED','RUN COMPLETED']:
        assert token in output
    for key,pat in [('Number of processes requested',r'1\b'),('Number of threads per process requested',r'10\b'),
                    ('Total number of cores requested',r'10\s*\(Shared Memory Parallel\)')]:
        assert re.search(key+r'\s*:\s*'+pat,output)
    for kind in ['WARNING','ERROR']:
        assert re.findall(rf'NUMBER OF {kind}\s+MESSAGES ENCOUNTERED=\s*(\d+)',output)==['0']
        assert f'*** {kind} ***' not in output
    last=0.
    def guard():
        nonlocal last
        host_check()
        if time.monotonic()-last>15:
            disks()
            last=time.monotonic()
    with ZipFile(run/'sector_fields.zip') as archive:
        record,count,field_error=replay(settings,lambda i,b:archive.read(f'{i:06d}.txt'),guard)
        assert len(archive.namelist())==count==terminal['native_blocks']
    cp=json.loads((run/'sector_checkpoint.json').read_text())
    assert cp['record']==terminal['record'] and cp['nonce']==terminal['nonce'] and cp['native_blocks']==count
    match=differences(terminal['record'],record)
    bal=balances(settings,record)
    assert match<1e-7 and max(map(abs,bal.values()))<1e-7
    result=dict(passed=True,job=job,case=settings['case'],native_thermal_blocks=count,
                replay_relative_difference=match,max_free_field_difference_K=field_error,balances=bal,
                utc=utc(),files={n:digest(run/n) for n in files},controller_sha256=expected['controller_sha256'],
                deck_sha256=expected['deck_sha256'],native_receipt_sha256=digest(run/'guest_terminal.json'),
                events=record['stats']['events'],terminal_s=record['state']['time'],qualification='Model verification only.')
    if settings['role']=='pilot':
        assert abs(record['state']['time']-settings['horizon_s'])<1e-10 and len(record['state']['virgin'])
    else:
        baseline=ROOT/'validation/sector_exposure_reduction.json'
        assert digest(baseline)==expected['independent_reference_sha256']
        ref=json.loads(baseline.read_text())['cases'][settings['case']]['runs'][0]
        target=ref['events']['exhaustion'][1]
        event=result['events']['exhaustion'][1]
        assert not record['state']['virgin'] and abs(event/target-1.)<expected['max_event_difference_fraction']
        assert result['events']['baseline_property_limit'][1]<event
        assert result['events']['backing_1000_C' if settings['case'].endswith('cf') else 'all_liquid'][1]<event
        result.update(reference_event_s=target,delta_event_s=event-target)
    atomic(ROOT/'validation'/('native_whole_sector_'+job+'.json'),result)


def fixture():
    from io import BytesIO
    from sector_wall import Sector
    summary={}
    for job in JOBS[:2]:
        _,settings=load_job(job)
        geom=settings['configuration']['geometry']
        def render(i,block):
            # Check real-constant assembly, free thermal boundaries and absence
            # of imposed degrees of freedom before this reaches the guest.
            macro=commands(block,geom,i).splitlines()
            weights=topology(block,geom)[4]
            assert not any(line.startswith('D,') for line in macro)
            assert macro.count('SOLVE')==1 and sum(x.startswith('IC,') for x in macro)==len(weights)*len(block.radii)
            assert all(float(x.split(',')[2])>0 for x in macro if x.startswith('R,'))
            field=np.repeat(banded(block),len(weights))
            out=BytesIO()
            np.savetxt(out,np.vstack(([i,block.dt],np.column_stack((np.arange(1,1+len(field)),field)))),fmt=['%12.0f','%25.16E'])
            return out.getvalue()
        record,count,error=replay(settings,render,host_check)
        def corrupt(i,b):
            if i>1: raise RuntimeError('Damaged field passed the first block')
            return render(i,b).splitlines(keepends=True)[0]+render(i,b).split(b'\n',2)[2]
        try: replay(settings,corrupt,host_check)
        except ValueError: pass
        else: raise AssertionError('Accepted missing node')
        summary[job]=dict(blocks=count,max_field_error_K=error,energy_error=balances(settings,record)['energy_relative'])
    atomic(ROOT/'validation/sector_pilot_fixtures.json',dict(synthetic_only=True,summary=summary,
           archive_sha256=digest(PACKAGE/'controller.zip'),auditor_sha256=digest(Path(__file__))))
    print(summary)


if __name__=='__main__': disks();fixture()

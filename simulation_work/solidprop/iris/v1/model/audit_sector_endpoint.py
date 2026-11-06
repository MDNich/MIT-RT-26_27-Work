"""Replay free nodal fields using the exact sealed endpoint controller, in a fresh process."""
import argparse
import hashlib
from io import BytesIO
import json
import re
import sys
import time
import uuid
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from ops import ROOT, TMP, UNC, atomic, disks, guest, host_check, utc


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        h=hashlib.sha256()
        for chunk in iter(lambda:stream.read(4*1024*1024),b''): h.update(chunk)
        return h.hexdigest()


SMP_NOTICE = (
    'During this session a solution was performed using 10 CPU cores in '
    'shared-memory parallel (SMP) mode (-np 10). It is strongly '
    'recommended to use distributed-memory parallel (DMP) mode instead '
    '(-dis -np 10). DMP mode typically outperforms SMP mode, even when '
    'running on a single system. For more information, see the Mechanical '
    'APDL Parallel Processing Guide in the Ansys Help system.'
)


def check_log_messages(log):
    for kind in ('ERROR','WARNING'):
        if re.findall(rf'NUMBER OF {kind}\s+MESSAGES ENCOUNTERED=\s*(\d+)',log)!=['0']:
            raise ValueError(f'Nonzero or missing solver {kind.lower()} count')
    if '*** ERROR ***' in log:
        raise ValueError('Native solver reported an error')
    if '*** WARNING ***' not in log:
        return []
    before, marker, after=log.partition('*** WARNING ***')
    header, _, tail=after.partition('\n')
    body, separator, stats=tail.partition('+--------------------- M A P D L   S T A T I S T I C S')
    ordered=re.search(r'IRIS_WHOLE_SECTOR_RETURNED\s+EXIT MAPDL WITHOUT SAVING DATABASE\s+'
                      r'NUMBER OF WARNING MESSAGES ENCOUNTERED=\s*0\s+NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\s*$',before)
    if (not ordered or not separator or log.count(marker)!=1 or not re.fullmatch(
            r'\s*ELAPSED TIME\s*=\s*[\d.]+\s+TIME=\s*\d+:\d+:\d+\s*',header)
            or ' '.join(body.split())!=SMP_NOTICE or 'RUN COMPLETED' not in stats):
        raise ValueError('Unclassified native warning or warning during solution')
    return ['Ten-core SMP performance recommendation after solver exit and zero message counts']


def guest_replay(job,run):
    token='replay_'+uuid.uuid4().hex
    script=UNC+r'\model\replay_archived_sector.py'
    mirror=UNC+'\\ansystmp\\runs\\'+run.name
    executable=r'C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe'
    out=run/(token+'.json')
    err=run/(token+'.err')
    # Start only a postprocessor, return promptly so the storage watcher retains guest access.
    command=(f"$p=Start-Process -PassThru -FilePath '{executable}' -ArgumentList @('-B','{script}','{job}') "
             f"-RedirectStandardOutput '{mirror}\\{out.name}' -RedirectStandardError '{mirror}\\{err.name}';$p.Id")
    pid=int(guest(command))
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        host_check()
        time.sleep(2)
        if out.exists() and out.stat().st_size:
            try:
                return read(out)
            except json.JSONDecodeError:
                pass
        if err.exists() and err.stat().st_size:
            raise ValueError('Guest field replay: '+err.read_text(errors='replace')[-1500:])
    raise TimeoutError(f'Inspect guest postprocessor PID {pid} and {out.name}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('fixture','audit'))
    parser.add_argument('job',nargs='?')
    parser.add_argument('--package',type=Path,default=ROOT/'configs/native_verification/whole_sector_r2')
    args=parser.parse_args()
    disks()
    package=args.package.resolve()
    manifest=read(package/'manifest.json')
    for file,expected in manifest.items():
        assert sha(package/file)==expected,file
    archive=package/'controller.zip'
    sys.path.insert(0,str(archive))
    from sector_exposure import balances
    from sector_wall import banded
    from sector_mapdl import topology
    from audit_sector_exposures import replay, differences
    for module in ('sector_exposure','sector_wall','sector_mapdl'):
        assert sys.modules[module].__file__.startswith(str(archive)+'/')
    last=0.
    def guard():
        nonlocal last
        host_check()
        if time.monotonic()-last>15:
            disks()
            last=time.monotonic()
    def assess(job,settings,record):
        expected=read(package/(job+'.json'))
        error=balances(settings,record)
        assert max(map(abs,error.values()))<expected['max_balance_relative']
        events=record['stats']['events']
        end=record['state']['time']
        if settings['role']=='startup':
            assert abs(end-.1)<1e-10 and record['state']['virgin'] and 'exhaustion' not in events
        else:
            assert not record['state']['virgin'] and events['exhaustion'][1]==end
            assert abs(end-expected['reference_end_s'])<expected['max_event_relative']*(expected['reference_end_s']-expected['donor_start_s'])
            if settings['role']=='whole':
                assert events['baseline_property_limit'][1]<end and events['backing_1000_C' if settings['case'].endswith('cf') else 'all_liquid'][1]<end
        return dict(balances=error,terminal_s=end,events=events,
                    native_interval_start_s=expected['donor_start_s'],role=settings['role'],case=settings['case'])
    if args.action=='fixture':
        checks={}
        for job in ('start2al','start2cf','end2sa','end2sc','end2ba','end2bc'):
            settings=read(package/(job+'_settings.json'))
            def synthetic(seq,block):
                width=len(topology(block,settings['configuration']['geometry'])[4])
                field=np.repeat(banded(block),width)
                out=BytesIO()
                np.savetxt(out,np.vstack(([seq,block.dt],np.column_stack((np.arange(1,len(field)+1),field)))),
                           fmt=['%12.0f','%25.16E'])
                return out.getvalue()
            record,count,max_error=replay(settings,synthetic,guard)
            assert settings==read(package/(job+'_settings.json'))
            checks[job]=dict(blocks=count,max_error_K=max_error,**assess(job,settings,record))
        receipt=dict(synthetic_only=True,archive_sha256=sha(archive),manifest_sha256=sha(package/'manifest.json'),
                     auditor_sha256=sha(Path(__file__)),cases=checks)
        output=(ROOT/'validation' if args.package.resolve().parent==(ROOT/'configs/native_verification') else package.parent)
        atomic(output/'sector_endpoint_fixtures.json',receipt)
        return
    job=args.job
    assert job and job+'.inp' in manifest
    run=TMP/'runs'/('sector_'+job)
    settings=read(package/(job+'_settings.json'))
    receipt=read(run/'guest_terminal.json')
    terminal=read(run/'sector_terminal.json')
    intent=read(run/'intent.json')
    assert terminal['settings']==settings and terminal['controller_sha256']==sha(archive)
    assert terminal['nonce']==intent['nonce']==receipt['nonce']==read(run/'guest_launch.json')['nonce']
    assert receipt['exit_code']==0 and receipt['job']==terminal['job']==intent['case']==job
    assert sha(run/(job+'.inp'))==manifest[job+'.inp']==receipt['guest_input_sha256'].lower()==intent['deck_sha256']
    assert not (run/'sector_failure.json').exists()
    files={name:sha(run/name) for name in [job+'.out','sector_fields.zip','sector_terminal.json']}
    assert all(v==receipt['guest_sha256'][k].lower() for k,v in files.items())
    log=(run/(job+'.out')).read_text(errors='replace')
    assert 'IRIS_WHOLE_SECTOR_RETURNED' in log and 'RUN COMPLETED' in log
    shutdown_advisories=check_log_messages(log)
    for key,pat in [('Number of processes requested',r'1\b'),('Number of threads per process requested',r'10\b'),
                    ('Total number of cores requested',r'10\s*\(Shared Memory Parallel\)')]:
        assert re.search(key+r'\s*:\s*'+pat,log)
    replay_proof=None
    if settings['role']=='whole':
        proof=guest_replay(job,run)
        assert proof['job']==job and proof['controller_sha256']==sha(archive)
        assert proof['source_sha256']==sha(ROOT/'model/replay_archived_sector.py')
        assert proof['field_sha256']==files['sector_fields.zip'] and proof['terminal_sha256']==files['sector_terminal.json']
        assert proof['settings_sha256']==manifest[job+'_settings.json']
        record=proof.pop('record')
        count,max_error=proof['native_blocks'],proof['max_field_error_K']
        assert count==terminal['native_blocks'] and max_error<=2e-6 and proof['replay_difference']<1e-7
        replay_proof=proof
    else:
        with ZipFile(run/'sector_fields.zip') as fields:
            record,count,max_error=replay(settings,lambda i,b:fields.read(f'{i:06d}.txt'),guard)
            assert len(fields.namelist())==count==terminal['native_blocks']
    checkpoint=read(run/'sector_checkpoint.json')
    assert checkpoint['nonce']==receipt['nonce'] and checkpoint['native_blocks']==count
    assert differences(checkpoint['record'],record)<1e-7 and differences(terminal['record'],record)<1e-7
    out=assess(job,settings,record)
    assert differences(terminal['balances'],out['balances'])<1e-7
    atomic(ROOT/'validation'/('native_sector_r2_'+job+'.json'),dict(
        passed=True,job=job,utc=utc(),strict_guest_replay=replay_proof,shutdown_advisories=shutdown_advisories,native_blocks=count,max_field_error_K=max_error,files=files,
        archive_sha256=sha(archive),auditor_sha256=sha(Path(__file__)),terminal_sha256=sha(run/'guest_terminal.json'),
        settings_sha256=manifest[job+'_settings.json'],**out))


if __name__=='__main__':
    main()

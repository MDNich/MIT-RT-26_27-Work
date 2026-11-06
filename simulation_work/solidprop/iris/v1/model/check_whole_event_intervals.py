"""Isolate mesh and time effects in the independent radial reduction of the sealed R2 native controller."""
import fcntl
import hashlib
import json
import sys
import time
from pathlib import Path

from ops import ROOT, TMP, StorageLimitError, atomic, disks, host_check, stop_runs, utc

PACKAGE = ROOT/'configs/native_verification/whole_sector_r2'
WORK = TMP/'whole_event_intervals'
LEVELS = [(80,.04), (160,.04), (160,.02), (160,.01), (320,.01), (320,.005), (320,.0025), (640,.0025)]
JOBS = ('wall2sa','wall2sc','wall2ba','wall2bc')


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    disks()
    manifest = read(PACKAGE/'manifest.json')
    archive = PACKAGE/'controller.zip'
    signature = digest(archive)
    assert signature == manifest['controller.zip']
    sys.path.insert(0,str(archive))
    from sector_exposure import balances, integrate
    from sector_wall import banded
    assert all(sys.modules[m].__file__.startswith(str(archive)+'/') for m in ('sector_exposure','sector_wall','sector_terminal_step'))
    last_check = 0.
    def guard():
        nonlocal last_check
        host_check()
        if time.monotonic()-last_check > 15.:
            disks()
            last_check=time.monotonic()
    WORK.mkdir(exist_ok=True)
    output = {}
    for job in JOBS:
        path = PACKAGE/(job+'_settings.json')
        assert digest(path) == manifest[path.name]
        base = read(path)
        case = base['case']
        cf = case.endswith('_cf')
        tag = case + ('_reacting_fine' if cf else '_phase_n640_ms20_mK500')
        material = 'cf' if cf else 'aluminium'
        audit=read(ROOT/f'validation/{material}_backing_audit.json')['records'][tag]
        reference=ROOT/f'validation/{material}_backing_cases'/(tag+'.json')
        assert digest(reference)==audit['sha256' if cf else 'record_sha256']
        fv=read(reference)['event_bracket_s']
        rows=[]
        for n, dt in LEVELS:
            guard()
            settings=dict(base,n=n,nc=n//4,dt_s=dt)
            record_path=WORK/f'{job}_n{n}_us{round(dt*1e6)}.json'
            identity=dict(archive_sha256=signature,base_settings_sha256=digest(path),n=n,nc=n//4,dt_s=dt,
                          study_sha256=digest(Path(__file__)))
            if record_path.exists():
                saved=read(record_path)
                assert saved['identity']==identity
                result=saved['result']
            else:
                atomic(WORK/'status.json',dict(job=job,n=n,dt_s=dt,utc=utc()))
                result=integrate(settings,banded,guard)
                atomic(record_path,dict(identity=identity,result=result))
            errors=balances(settings,result)
            stats=result['stats']
            interval=stats['events']['exhaustion']
            assert result['state']['virgin']==[] and interval[1]==result['state']['time']
            assert 0 < interval[1]-interval[0] <= dt+1e-8 and max(map(abs,errors.values()))<1e-7
            gap=max(0.,max(interval[0],fv[0])-min(interval[1],fv[1]))
            rows.append(dict(**identity,event_bracket_s=interval,residuals=errors,
                             steps=stats['steps'],raw_interval_gap_s=gap,
                             signed_end_difference_s=interval[1]-fv[1],record_sha256=digest(record_path)))
            print(job,n,dt,interval,'FV gap',gap,flush=True)
        output[job]=dict(case=case,independent_FV_bracket_s=fv,independent_FV_sha256=digest(reference),runs=rows)
    target=ROOT/'validation/whole_event_interval_refinement.json'
    atomic(target,dict(source_sha256=digest(Path(__file__)),native=False,eligible_for_motor_lifetime=False,cases=output,
                       scope='Independent radial reduction of the sealed native equations; separate field and FV models. Terminal time intervals are numerical step intervals.'))
    atomic(WORK/'complete.json',dict(utc=utc(),sha256=digest(target)))


if __name__=='__main__':
    try:
        with (TMP/'continuous_heating/worker.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            check()
    except StorageLimitError as error:
        stop_runs(str(error))
        raise

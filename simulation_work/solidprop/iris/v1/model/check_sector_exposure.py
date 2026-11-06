"""Host-only audit of the axisymmetric reduction of the proposed native sector.

Separate time and mesh changes. Require conservations, material scope flags,
restart agreement, and event agreement with the independently audited FV wall.
"""
import fcntl
import json
import time
from pathlib import Path
from continuous_heating_campaign import digest
from moving_surface_campaign import SHARED
from ops import ROOT,TMP,StorageLimitError,atomic,disks,host_check,stop_runs,utc
from sector_exposure import balances,integrate
from sector_wall import banded

FILES = ['sector_exposure','sector_wall','aluminium_phase_enthalpy','cf_backing_response','coupler',
         'diagnose_cf_backing','moving_surface_remap','moving_surface_thermochemistry','radial_model']
PLAN=ROOT/'configs/moving_surface_campaign.json'
OUT=ROOT/'validation/sector_exposure_reduction.json'


def main():
    disks()
    inputs={name:digest(ROOT/f'model/{name}.py') for name in [*FILES,'check_sector_exposure']}
    root=TMP/'sector_reduction'/inputs['check_sector_exposure'][:12]
    root.mkdir(exist_ok=True,parents=True)
    last=0
    def guard():
        nonlocal last
        host_check()
        if time.monotonic()-last>15:
            disks()
            last=time.monotonic()
    compare={}
    for case in json.loads(PLAN.read_text())['cases'][:4]:
        name=case['case']
        cfg=case['configuration']
        material='cf' if cfg['case_material']=='cf' else 'aluminium'
        audit=ROOT/f'validation/{material}_backing_audit.json'
        data=json.loads(audit.read_text())
        reference = name + ('_reacting_fine' if material=='cf' else '_phase_n640_ms20_mK500')
        fv=data['records'][reference]['events']['exhaustion'][1]
        cases=[]
        for n,dt in [(80,.04),(160,.04),(160,.02)]:
            tag=f'{name}_{n}_{dt}'
            settings=dict(configuration=cfg,n=n,nc=n//4,dt_s=dt,horizon_s=220.)
            target=root/(tag+'.json')
            # Bind a completed cache to both executable and exact inputs.
            if target.exists():
                cached=json.loads(target.read_text())
                if cached['sources']!=inputs or cached['settings']!=settings: raise ValueError('Stale reduction '+tag)
                record=cached['record']
            else:
                record=integrate(settings,banded,guard)
                atomic(target,dict(sources=inputs,settings=settings,record=record))
            stats=record['stats']
            flags=stats['events']
            event=flags['exhaustion'][1]
            assert flags['baseline_property_limit'][1]<event
            assert flags['backing_1000_C' if material=='cf' else 'all_liquid'][1]<event
            errors=balances(settings,record)
            assert max(map(abs,errors.values()))<1e-7 and record['state']['virgin']==[]
            cases.append(dict(n=n,nc=n//4,dt_s=dt,steps=stats['steps'],cutbacks=stats['cutbacks'],
                              events=flags,balance_errors=errors,record_sha256=digest(target)))
            print(tag,event,flush=True)
        args=dict(configuration=cfg,n=80,nc=20,dt_s=.02,horizon_s=.5)
        first=integrate(args,banded,guard,interrupt=lambda s:s.time>=.2)
        resumed=integrate(args,banded,guard,initial_record=json.loads(json.dumps(first)))
        straight=integrate(args,banded,guard)
        assert resumed==straight
        final=cases[-1]['events']['exhaustion'][1]
        changes=[abs(a['events']['exhaustion'][1]-b['events']['exhaustion'][1]) for a,b in zip(cases,cases[1:])]
        assert max(changes)<.01*final and abs(final-fv)<.01*fv
        compare[name]=dict(runs=cases,FV_reference_s=fv,FV_audit_sha256=digest(audit),
                           final_minus_FV_s=final-fv,mesh_and_time_changes_s=changes,restart_identical=True)
    summary=dict(passed=True,checked_utc=utc(),sources=inputs,config_sha256=digest(PLAN),cases=compare,
                 scope='Independent FE reduction only. All endpoints occur beyond baseline backing scope.')
    atomic(OUT,summary)


if __name__=='__main__':
    try:
        with (SHARED/'worker.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            main()
    except StorageLimitError as exc:
        stop_runs(str(exc))
        raise

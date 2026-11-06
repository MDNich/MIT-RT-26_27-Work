"""Repeat previously specified pressure, radiation and gas-temperature probes with evolving casings."""
import argparse
from copy import deepcopy
import fcntl
import os
from pathlib import Path
import signal
import time

from audit_backing_film import meets
from audit_moving_surface import compare
from backing_film_campaign import MATERIALS, inputs, parents, read
from compare_native_whole_exposures import compare_history
from continuous_heating_campaign import digest
from moving_surface_campaign import SHARED, stop_signal
from moving_surface_sensitivities import cases as scenario_changes
from ops import ROOT, TMP, StorageLimitError, atomic, disks, host_check, stop_runs, utc
from sector_exposure import integrate, balances
from sector_wall import banded

PLAN=ROOT/'configs/evolving_exposure_sensitivities.json'
WORK=TMP/'evolving_exposure_sensitivities'
OUT=ROOT/'validation/evolving_exposure_sensitivities.json'
SCENARIOS=('p600','p1000','rad10','rad30','gasdelta90','gasdelta110')


def prepare():
    disks()
    if PLAN.exists():
        raise FileExistsError(PLAN)
    earlier=read(ROOT/'configs/moving_surface_sensitivities.json')
    prior={(row['case'],row['scenario']):row for row in earlier['cases']}
    jobs=[]
    for name,parent in parents().items():
        changes=dict(scenario_changes(name))
        for scenario in SCENARIOS:
            change=changes[scenario]
            evidence=prior[name,scenario]['configuration']
            for section,properties in change.items():
                for key,value in properties.items():
                    assert evidence[section][key]==value and parent['configuration'][section][key]!=value
            jobs.append(dict(case=name,scenario=scenario,parent_tag=parent['tag'],change=change))
    signature=inputs()
    for mod in ('evolving_exposure_sensitivities','moving_surface_sensitivities','audit_backing_film',
                'audit_moving_surface','compare_native_whole_exposures','sector_wall','sector_exposure'):
        path=ROOT/f'model/{mod}.py'
        signature[str(path.relative_to(ROOT))]=digest(path)
    atomic(PLAN,dict(jobs=jobs,sources=signature,horizon_s=360.,
        profile_times_s=[0.,1.,7.,30.,60.,90.,120.,180.,240.,360.],
        fv_levels=[[320,.04],[640,.04],[640,.02]],mesh_followups=[[1280,.04],[2560,.04]],
        time_followups=[[640,.01],[640,.005],[640,.0025]],nodal=[160,.02],
        event_relative=.01,liner_mass_relative=1e-8,energy_relative=1e-6,
        scope='One changed physical input per case. Gas-excess temperature probes and effective emissivities are assumed. Pressure acts in the char kinetics only.'))


def solve_case(job,cfg,plan,signature,guard):
    material=MATERIALS[cfg['case_material']]
    prefix=job['case']+'_'+job['scenario']
    data=WORK/'cases'
    data.mkdir(parents=True,exist_ok=True)
    sources={}
    def finite_volume(level):
        guard()
        n,dt=level
        tag=f'{prefix}_n{n}_us{round(dt*1e6)}'
        settings=dict(tag=tag,configuration=cfg,n=n,nc=n//4,dt=dt)
        if not material.run_case(settings,plan,signature,WORK,data):
            raise InterruptedError('Independent checkpoint saved')
        path=data/(tag+'.json')
        rec=read(path)
        cp=WORK/(tag+'_checkpoint.json')
        assert rec['tag']==tag and rec['plan_sha256']==signature and rec['checkpoint_sha256']==digest(cp)
        assert rec['eligible_for_motor_lifetime'] is False and rec['history'][0]['time_s']==0.
        assert rec['stats']['max_mass_relative_error']<plan['liner_mass_relative']
        assert rec['stats']['max_energy_relative_error']<plan['energy_relative']
        sources[tag]=dict(record=digest(path),checkpoint=digest(cp))
        return rec

    coarse,mesh,fine=[finite_volume(level) for level in plan['fv_levels']]
    best=fine
    checks={}
    for axis,a,b in [('mesh',coarse,mesh),('time',mesh,fine)]:
        levels=iter(plan[axis+'_followups'])
        chain=[]
        while True:
            if a['status']=='HORIZON_WITH_LINER' or b['status']=='HORIZON_WITH_LINER':
                return dict(numerical_checks_passed=False,reason='Run retained liner at horizon',
                            observed_through_s=plan['horizon_s'],sources=sources)
            assert a['status']==b['status']=='SURROGATE_EXHAUSTION'
            agreement=compare(a,b)
            chain.append(dict(a=a['tag'],b=b['tag'],comparison=agreement))
            if meets(agreement):
                break
            level=next(levels,None)
            if level is None:
                break
            a,b=b,finite_volume(level)
            if axis=='time':
                best=b
        checks[axis]=dict(passed=meets(agreement),chain=chain)

    n,dt=plan['nodal']
    setting=dict(n=n,nc=n//4,dt_s=dt,configuration=cfg,horizon_s=plan['horizon_s'])
    path=data/(prefix+'_nodal.json')
    if path.exists():
        file=read(path)
        assert file['plan_sha256']==signature and file['settings']==setting
        nodal=file['record']
    else:
        nodal=integrate(setting,banded,guard)
        atomic(path,dict(plan_sha256=signature,settings=setting,record=nodal))
    balance=balances(setting,nodal)
    assert max(map(abs,balance.values()))<1e-7
    if nodal['state']['virgin']:
        return dict(numerical_checks_passed=False,reason='Nodal model retained liner at horizon',sources=sources,
                    observed_through_s=plan['horizon_s'],nodal_sha256=digest(path))
    ev=best['event_bracket_s']
    assert best['scope_bracket_s'][1]<ev[0]
    assert best['history'][-1]['remaining_mm']==0 and nodal['stats']['events']['exhaustion'][1]==nodal['state']['time']
    history=compare_history(nodal['stats']['samples'],best['history'])
    led=best['history'][-1]['ledger']
    ri=cfg['geometry']['inner_radius_m']
    film,rad=led['film_heat']/ri/1e6,led['radiation_heat']/ri/1e6
    assert film>0 and ((rad>0)==(cfg['heating']['hot_effective_emissivity']>0)) and rad>=0
    target=max(.02,.01*best['history'][0]['remaining_mm'])
    passed=all(r['passed'] for r in checks.values()) and abs(nodal['state']['time']/ev[1]-1)<plan['event_relative']
    return dict(numerical_checks_passed=bool(passed and history['differences']['remaining_mm']['max_abs']<=target),
                FV_tag=best['tag'],FV_event_s=ev[1],events=best['events'],FV_checks=checks,sources=sources,
                nodal_event_s=nodal['state']['time'],nodal_sha256=digest(path),nodal_balances=balance,
                common_history=history,thickness_limit_mm=target,film_dose_MJ_m2=film,radiation_dose_MJ_m2=rad)


def run():
    disks()
    plan=read(PLAN)
    signature=digest(PLAN)
    assert all(digest(ROOT/p)==sha for p,sha in plan['sources'].items())
    if (WORK/'complete.json').exists():
        done=read(WORK/'complete.json')
        assert done['plan_sha256']==signature and done['audit_sha256']==digest(OUT)
        return
    refs=parents()
    for sig in (signal.SIGTERM,signal.SIGINT):
        signal.signal(sig,stop_signal)
    last=0.
    def guard():
        nonlocal last
        host_check()
        if time.monotonic()-last>15:
            disks()
            last=time.monotonic()
    atomic(WORK/'worker.json',dict(pid=os.getpid(),utc=utc(),plan_sha256=signature))
    rows={}
    for job in plan['jobs']:
        parent=refs[job['case']]
        assert job['parent_tag']==parent['tag']
        cfg=deepcopy(parent['configuration'])
        for section,properties in job['change'].items():
            cfg[section].update(properties)
        key=job['case']+'_'+job['scenario']
        rows[key]=solve_case(job,cfg,plan,signature,guard)
        print(key,rows[key]['numerical_checks_passed'],rows[key].get('FV_event_s'),flush=True)
    atomic(OUT,dict(plan_sha256=signature,native=False,eligible_for_motor_lifetime=False,cases=rows))
    atomic(WORK/'complete.json',dict(plan_sha256=signature,audit_sha256=digest(OUT),utc=utc()))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    try:
        if parser.parse_args().action=='prepare':
            prepare()
        else:
            with (SHARED/'worker.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                run()
    except StorageLimitError as error:
        stop_runs(str(error))
        raise

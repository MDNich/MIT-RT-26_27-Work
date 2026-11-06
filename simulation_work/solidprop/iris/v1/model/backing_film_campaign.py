"""Isolate gas-film sensitivity for the two evolving backing models.

The sealed plan refers to exact previously audited configurations. The altered
coefficient acts before blowing correction. Heat flux, surface temperature,
gas production and case state are solved again from ignition in each job.
"""
import argparse
import copy
import fcntl
import json
import os
import signal

import aluminium_backing_campaign as aluminium
import cf_backing_campaign as carbon
from continuous_heating_campaign import digest
import moving_surface_campaign as moving
from ops import ROOT,TMP,StorageLimitError,atomic,disks,host_check,stop_runs,utc

PLAN=ROOT/'configs/evolving_backing_film.json'
WORK=TMP/'evolving_backing_film'
DATA=WORK/'cases'
PROOF=ROOT/'validation/evolving_backing_film_audit.json'
MATERIALS={'al':aluminium,'cf':carbon}
LEVELS={'mesh':(320,80,.04),'time':(640,160,.04),'fine':(640,160,.02)}


def read(path):
    return json.loads(path.read_text())


def inputs():
    paths=[aluminium.PLAN, carbon.PLAN,ROOT/'configs/moving_surface_sensitivities.json',
           ROOT/'validation/aluminium_backing_audit.json',ROOT/'validation/cf_backing_audit.json']
    sources={**aluminium.sources(),**carbon.sources(),'backing_film_campaign':digest(__file__)}
    paths += [ROOT/f'model/{name}.py' for name in sources]
    return {str(path.relative_to(ROOT)):digest(path) for path in paths}


def parents():
    cases={}
    for material,module in MATERIALS.items():
        plan=read(module.PLAN)
        if plan['sources']!=module.sources(): raise ValueError('Changed backing implementation')
        for row in plan['cases']:
            if row['tag'].endswith(('_phase_n640_ms20_mK500','_reacting_fine')):
                cases[row['case']]=row
    if len(cases)!=4: raise ValueError('Expected four independent references')
    return cases


def prepare():
    disks()
    references=parents()
    prior=read(ROOT/'configs/moving_surface_sensitivities.json')
    jobs=[]
    # Take the coefficient values directly from the earlier one-factor study.
    for case,row in references.items():
        for h in [500,2000]:
            previous=[r for r in prior['cases'] if r['case']==case and r['scenario']==f'h{h}']
            assert len(previous)==1 and previous[0]['configuration']['heating']['h0_W_m2_K']==h
            for level,(n,nc,dt) in LEVELS.items():
                jobs.append(dict(case=case,parent_tag=row['tag'],h0=h,level=level,n=n,nc=nc,dt=dt,
                                 tag=f'{case}_film{h}_{level}'))
    plan=dict(inputs=inputs(),cases=jobs,horizon_s=360.,profile_times_s=[0.,1.,7.,30.,60.,90.,120.,150.,210.,270.,360.],
              limits=dict(mass_relative=1e-8,heat_relative=1e-6,event_relative=.05,thickness_mm=.02,
                          thickness_relative=.01,require_FV_pair_bracket_overlap=True),
              qualification='Separate sustained scenarios at 2504 K and 800 psi. Only the uncorrected film coefficient changes. '
                            'Retained backing geometry past material flags. A simulated endpoint is not a physical service limit.')
    if PLAN.exists(): raise FileExistsError('Sealed film study already exists')
    atomic(PLAN,plan)


def resolve(job,references):
    source=references[job['case']]
    if source['tag']!=job['parent_tag']: raise ValueError('Incorrect baseline tag')
    config=copy.deepcopy(source['configuration'])
    assert config['heating']['h0_W_m2_K']==1000.
    config['heating']['h0_W_m2_K']=job['h0']
    return dict(**job,configuration=config)


def verified_plan():
    plan=read(PLAN)
    if plan['inputs']!=inputs(): raise RuntimeError('Sealed film sources changed')
    return plan,digest(PLAN),parents()


def run():
    disks()
    plan,sha,refs=verified_plan()
    with (moving.SHARED/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (WORK/'complete.json').exists():
            complete=read(WORK/'complete.json')
            assert complete['plan_sha256']==sha and complete['cases']==len(plan['cases'])
            return
        for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,moving.stop_signal)
        DATA.mkdir(parents=True,exist_ok=True)
        atomic(WORK/'worker.json',dict(pid=os.getpid(),utc=utc(),plan_sha256=sha))
        try:
            for case in plan['cases']:
                row=resolve(case,refs)
                module=MATERIALS[row['configuration']['case_material']]
                if not module.run_case(row,plan,sha,WORK,DATA): return
                print(row['tag'],flush=True)
            atomic(WORK/'complete.json',dict(cases=len(plan['cases']),utc=utc(),plan_sha256=sha))
        except StorageLimitError: raise
        except Exception as exc:
            host_check()
            atomic(WORK/'error.json',dict(case=case['tag'],error=repr(exc),utc=utc()))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run'])
    try:
        if parser.parse_args().action=='prepare': prepare()
        else: run()
    except StorageLimitError as err:
        stop_runs(str(err))
        raise

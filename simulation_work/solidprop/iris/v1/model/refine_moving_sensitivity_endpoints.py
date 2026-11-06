"""Time and space refinements for the lowest and highest recorded one-factor events."""
import argparse
import copy
import fcntl
import json
import os
import signal

import moving_surface_campaign as campaign
from continuous_heating_campaign import digest
from moving_surface_sensitivities import PLAN as SCREEN, OUT as SCREEN_OUT, WORK as SCREEN_WORK
from audit_moving_surface import audit_case, compare
from ops import ROOT, TMP, atomic, disks, host_check, stop_runs, StorageLimitError, utc

PLAN=ROOT/'configs/moving_surface_sensitivity_endpoints.json'
AUDIT=ROOT/'validation/moving_surface_sensitivity_audit.json'
WORK=TMP/'moving_surface_endpoints'
OUT=ROOT/'validation/moving_surface_endpoints'


def prepare():
    disks()
    if PLAN.exists(): raise FileExistsError('Endpoint plan is immutable')
    ref=json.loads(AUDIT.read_text()); base=json.loads(SCREEN.read_text())
    assert ref['plan_sha256']==digest(SCREEN)
    rows=[]
    for item in base['cases']:
        if item['scenario'] not in ref['extreme_scenarios'][item['case']]: continue
        for dt in (.04,.02):
            job=copy.deepcopy(item)
            job.update(n=640,nc=160,dt=dt,screen_tag=item['tag'],tag=f"{item['tag']}_640_{round(dt*100):02d}")
            rows.append(job)
    assert len(rows)==16
    atomic(PLAN,dict(cases=rows,horizon_s=base['horizon_s'],profile_times_s=base['profile_times_s'],
                     screen_sha256=digest(SCREEN),screen_audit_sha256=digest(AUDIT),created_utc=utc(),
                     sources=campaign.sources(),worker_sha256=digest(__file__),
                     qualification='Each case uses the actual two extrema of its one-factor screen. '
                        'First double the radial counts at matched step, then halve the step on that fine mesh.'))


def audit(plan,sha):
    assert json.loads((WORK/'complete.json').read_text())['plan_sha256']==sha
    screen=json.loads(SCREEN.read_text())
    screen_jobs={x['tag']:x for x in screen['cases']}
    records,groups={},{}
    for item in plan['cases']:
        tag=item['screen_tag']; base=screen_jobs[tag]
        assert item['configuration']==base['configuration'] and item['n']==640 and item['nc']==160
        if tag not in groups:
            coarse,_=audit_case(base,screen,plan['screen_sha256'],SCREEN_WORK,SCREEN_OUT)
            groups[tag]={0:coarse}
        data,rec=audit_case(item,plan,sha,WORK,OUT)
        records[item['tag']]=rec;groups[tag][item['dt']]=data
    pairs={tag:dict(space=compare(g[0],g[.04]),time=compare(g[.04],g[.02])) for tag,g in groups.items()}
    atomic(ROOT/'validation/moving_surface_endpoint_audit.json',dict(checked_utc=utc(),plan_sha256=sha,
           records=records,comparisons=pairs,physical_lifetime=False,native_verified=False,
           qualification='Numerical resolution of selected one-factor extrema only. '
                         'No joint input distribution, structural failure prediction or measured motor burnthrough.'))
    for tag,g in pairs.items(): print(tag,[(p['event_difference_s'],p['brackets_overlap']) for p in g.values()])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','run','audit'])
    action=parser.parse_args().action
    if action=='prepare':
        prepare()
        return
    disks()
    plan=json.loads(PLAN.read_text()); sha=digest(PLAN)
    assert plan['sources']==campaign.sources() and plan['worker_sha256']==digest(__file__)
    assert plan['screen_sha256']==digest(SCREEN) and plan['screen_audit_sha256']==digest(AUDIT)
    if action=='audit':
        audit(plan,sha)
        return
    with (campaign.SHARED/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,campaign.stop_signal)
        atomic(WORK/'worker.json',dict(pid=os.getpid(),started_utc=utc(),plan_sha256=sha))
        try:
            for item in plan['cases']:
                if not campaign.run_case(item,plan,sha,WORK,OUT): return
        except StorageLimitError as exc:
            stop_runs(str(exc));raise
        except Exception as exc:
            host_check();atomic(WORK/'error.json',dict(tag=item['tag'],utc=utc(),error=repr(exc)));raise
        atomic(WORK/'complete.json',dict(plan_sha256=sha,utc=utc(),cases=len(plan['cases'])))


if __name__=='__main__': main()

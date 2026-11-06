"""Serial, restartable continuous-heating comparisons with a reacting retained CF backing."""
from recover_matched_intervals import output_step
import argparse
import bisect
import copy
import fcntl
import json
import os
from pathlib import Path
import signal
import time

import numpy as np

from cf_backing_wall import CarbonBackingWall
from continuous_heating_campaign import digest
import moving_surface_campaign as parent
from moving_surface_boundary import solve_face
from moving_surface_conduction import thermal_geometry
from ops import ROOT,TMP,StorageLimitError,atomic,disks,host_check,stop_runs,utc

PLAN = ROOT/'configs/cf_backing_campaign.json'
COUPON = ROOT/'validation/cf_backing_coupon.json'
OUT = ROOT/'validation/cf_backing_cases'
WORK = TMP/'cf_backing_campaign'
BACK_FLOWS = ('backing_gas','backing_gas_heat','backing_reaction_heat')
MILESTONES = ('property_flag','inner_pool_half','outer_pool_half','first_1000C','exhaustion')


def sources():
    extras = ('cf_backing_campaign','cf_backing_wall','cf_backing_response','diagnose_cf_backing')
    return {**parent.sources(),**{n:digest(ROOT/f'model/{n}.py') for n in extras}}


def prepare():
    disks()
    if PLAN.exists(): raise FileExistsError('CF setup already sealed')
    check = json.loads(COUPON.read_text())
    assert check['passed'] and all(digest(ROOT/f'model/{n}.py')==h for n,h in check['sources'].items())
    original = json.loads(parent.PLAN.read_text())
    jobs = []
    for base in original['cases']:
        if base['n']!=640 or base['dt']!=.02 or base['configuration']['case_material']!='cf': continue
        for n,dt,catalyst,label in [(320,.04,7.4886,'mesh'),(640,.04,7.4886,'time'),(640,.02,7.4886,'fine'),
                                    (640,.02,10.**(-.8744),'alternate')]:
            item = copy.deepcopy(base)
            item.update(n=n,nc=n//4,dt=dt,nominal_tag=base['tag'],variant=label,tag=f"{base['case']}_reacting_{label}")
            item['configuration']['cf_catalyst'] = catalyst
            jobs.append(item)
    assert len(jobs)==8
    atomic(PLAN,dict(created_utc=utc(),sources=sources(),parent_sha256=digest(parent.PLAN),coupon_sha256=digest(COUPON),
         cases=jobs,profile_times_s=original['profile_times_s'],horizon_s=original['horizon_s'],
         criteria=dict(relative_event=.05,thickness_relative=.01,thickness_floor_mm=.02,require_bracket_overlap=True,
                       mass_relative=1e-8,energy_relative=1e-6),
         qualification='Fixed-volume T700/M21 backing in inert atmosphere, separate local vent; no delamination, '
         'bond response or pressure containment. Endpoint-held specific heat and normal conductivity. '
         'Record 150 C baseline flag and 1000 C literature ceiling separately. Liner and chamber match nominal.'))


def run_case(item,plan,sha,work,out,pause_after=None):
    disks()
    tag,cfg = item['tag'],item['configuration']
    checkpoint=work/(tag+'_checkpoint.json')
    record=out/(tag+'.json')
    if record.exists():
        d=json.loads(record.read_text())
        assert d['plan_sha256']==sha and d['checkpoint_sha256']==digest(checkpoint)
        return True
    w=CarbonBackingWall(cfg,item['n'],item['nc'])
    s=w.initial()
    paths=np.zeros((2,item['nc']))
    m0,h0=w.inventory(s)
    back0=sum(w.original_mass)
    led=dict.fromkeys((*parent.FLOWS,*BACK_FLOWS),0.)
    events=dict.fromkeys(MILESTONES)
    stats=dict(steps=0,max_mass_relative_error=0.,max_energy_relative_error=0.)
    def point(face,interface,outer,speed):
        return dict(**parent.point(w,s,face,interface,outer,speed,led),
                    backing_retained_kg_per_rad_m=float(sum(w.case_mass)),
                    inner_pool=float(paths[:,0].sum()),outer_pool=float(paths[:,-1].sum()),
                    max_backing_C=float(max(interface,outer,max(s.case_C))))
    def profile():
        return {**parent.profile(w,s),'backing_paths':paths.tolist()}
    centres,vol,_=thermal_geometry(s.liner_edges,np.ones(len(s.virgin)))
    face=solve_face(s.case_C[0],s.virgin[0]/vol[0],0.,w.inner,centres[0],0.,cfg)
    history=[point(face.temperature_C,s.case_C[0],s.case_C[-1],0.)]
    profiles=[profile()]
    if checkpoint.exists():
        cp=json.loads(checkpoint.read_text())
        assert cp['plan_sha256']==sha and cp['tag']==tag
        s=parent.decode(cp['state'])
        paths=np.array(cp['paths'])
        w.activate(paths)
        led,events,stats,history,profiles=(cp[k] for k in ('ledger','events','stats','history','profiles'))
    def save(status):
        host_check()
        atomic(checkpoint,dict(tag=tag,plan_sha256=sha,state=parent.encode(s),paths=paths.tolist(),ledger=led,
                               events=events,stats=stats,history=history,profiles=profiles))
        atomic(work/'status.json',dict(utc=utc(),tag=tag,time_s=s.time,status=status,events=events))
    save('RUNNING')
    saved=time.monotonic()
    horizon=plan['horizon_s']
    targets=sorted(set(np.arange(.5,horizon,.5).tolist()+[.00625,.0125,.025,.05,.1,.2,horizon]+
                       [t for t in plan['profile_times_s'] if 0<t<=horizon]))
    while len(s.virgin) and s.time<horizon-1e-10:
        if stats['steps']%128==0: host_check()
        if parent.STOP or (pause_after is not None and stats['steps']>=pause_after):
            save('PAUSED')
            return False
        target=targets[bisect.bisect_right(targets,s.time+1e-10)]
        before=s.time
        b=w.coupled_step(s,paths,output_step(s.time,target,item['dt']))
        a=b.thermal
        s,paths=a.state,b.paths
        for k in parent.FLOWS: led[k]+=getattr(a,k)
        for k in BACK_FLOWS: led[k]+=getattr(b,k)
        stats['steps']+=1
        m,h=w.inventory(s)
        dm=abs(m+sum(led[k] for k in parent.FLOWS[:3])-m0)/m0
        dm=max(dm,abs(sum(w.case_mass)+led['backing_gas']-back0)/back0)
        dh=abs(h-h0+sum(led[k] for k in parent.FLOWS[5:10])+led['backing_gas_heat']-
               led['backing_reaction_heat']-led['film_heat']-led['radiation_heat'])
        dh/=max(1.,abs(led['film_heat'])+abs(led['radiation_heat']),abs(h0))
        if dm>1e-8 or dh>1e-6: raise RuntimeError(f'Coupled balance failed: {dm}, {dh}')
        stats['max_mass_relative_error']=max(dm,stats['max_mass_relative_error'])
        stats['max_energy_relative_error']=max(dh,stats['max_energy_relative_error'])
        flags=(a.case_interface_C>=cfg['case_property_limit_C'],sum(paths[:,0])>=.5,sum(paths[:,-1])>=.5,
               max(a.case_interface_C,a.outer_C,max(s.case_C))>=1000.,len(s.virgin)==0)
        crossed=False
        for key,flag in zip(MILESTONES,flags):
            if events[key] is None and flag:
                events[key]=[before,s.time]
                crossed=True
        if crossed or abs(s.time-target)<1e-10:
            history.append(point(a.face_C,a.case_interface_C,a.outer_C,a.speed))
        if crossed or any(abs(s.time-t)<1e-10 for t in plan['profile_times_s']): profiles.append(profile())
        if time.monotonic()-saved>15.:
            disks()
            save('RUNNING')
            saved=time.monotonic()
    status='SURROGATE_EXHAUSTION' if events['exhaustion'] else 'HORIZON_WITH_LINER'
    save(status)
    atomic(record,dict(plan_sha256=sha,tag=tag,checkpoint_sha256=digest(checkpoint),status=status,
                       events=events,event_bracket_s=events['exhaustion'],scope_bracket_s=events['property_flag'],
                       history=history,profiles=profiles,stats=stats,eligible_for_motor_lifetime=False))
    return True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','run'))
    if p.parse_args().action=='prepare':
        prepare()
        return
    disks()
    plan=json.loads(PLAN.read_text())
    sha=digest(PLAN)
    assert plan['sources']==sources() and plan['parent_sha256']==digest(parent.PLAN) and plan['coupon_sha256']==digest(COUPON)
    with (parent.SHARED/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,parent.stop_signal)
        atomic(WORK/'worker.json',dict(pid=os.getpid(),utc=utc(),plan_sha256=sha))
        try:
            for item in plan['cases']:
                if not run_case(item,plan,sha,WORK,OUT): return
        except StorageLimitError as exc:
            stop_runs(str(exc))
            raise
        except Exception as exc:
            atomic(WORK/'error.json',dict(tag=item['tag'],utc=utc(),error=repr(exc)))
            raise
        atomic(WORK/'complete.json',dict(cases=len(plan['cases']),plan_sha256=sha,utc=utc()))


if __name__=='__main__': main()

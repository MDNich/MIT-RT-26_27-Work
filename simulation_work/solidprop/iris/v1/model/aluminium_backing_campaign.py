"""Serial, checkpointed moving-wall scenarios with a retained pure-Al caloric surrogate."""
import argparse
import bisect
import copy
import fcntl
import json
import os
import signal
import time

import numpy as np

from aluminium_backing_wall import AluminiumBackingWall
from continuous_heating_campaign import digest
import moving_surface_campaign as nominal
from moving_surface_boundary import solve_face
from moving_surface_conduction import thermal_geometry
from ops import ROOT, TMP, StorageLimitError, atomic, disks, host_check, stop_runs, utc

PLAN = ROOT/'configs/aluminium_backing_campaign.json'
COUPON = ROOT/'validation/aluminium_backing_coupon.json'
OUT = ROOT/'validation/aluminium_backing_cases'
WORK = TMP/'aluminium_backing_campaign'
MILESTONES = ('property_flag','first_melt','all_liquid','exhaustion')


def sources():
    return {**nominal.sources(), **{name:digest(ROOT/f'model/{name}.py') for name in
            ('aluminium_phase_enthalpy','aluminium_backing_wall','aluminium_backing_campaign')}}


def prepare():
    disks()
    if PLAN.exists(): raise FileExistsError('Aluminium backing inputs already sealed')
    coupon = json.loads(COUPON.read_text())
    assert coupon['passed'] and all(digest(ROOT/f'model/{n}.py')==v for n,v in coupon['sources'].items())
    parent = json.loads(nominal.PLAN.read_text())
    jobs = []
    for base in parent['cases']:
        if base['n']!=640 or base['dt']!=.02 or base['configuration']['case_material']!='al': continue
        for n,dt,width in [(320,.04,2.),(640,.04,2.),(640,.02,2.),(640,.02,1.),(640,.02,.5)]:
            item=copy.deepcopy(base)
            item.update(n=n,nc=n//4,dt=dt,nominal_tag=base['tag'],
                        tag=f"{base['case']}_phase_n{n}_ms{int(dt*1000)}_mK{int(width*1000)}")
            item['configuration']['al_fusion_width_K']=width
            jobs.append(item)
    assert len(jobs)==10
    atomic(PLAN,dict(created_utc=utc(),sources=sources(),cases=jobs,horizon_s=parent['horizon_s'],
        profile_times_s=parent['profile_times_s'],coupon_sha256=digest(COUPON),parent_sha256=digest(nominal.PLAN),
        qualification='Only Al caloric response changes. Inherited constant radial conductivity, fixed Al mass '
                      'and retained backing geometry through melting. Keep the earlier property flag.'))


def run_case(item,plan,sha,work,out,pause_after=None):
    disks()
    tag,cfg=item['tag'],item['configuration']
    w=AluminiumBackingWall(cfg,item['n'],item['nc'])
    cp_path,record=work/(tag+'_checkpoint.json'),out/(tag+'.json')
    if record.exists():
        d=json.loads(record.read_text())
        assert d['plan_sha256']==sha and d['checkpoint_sha256']==digest(cp_path)
        return True
    s=w.initial()
    m0,h0=w.inventory(s)
    totals=dict.fromkeys(nominal.FLOWS,0.)
    events=dict.fromkeys(MILESTONES)
    stats=dict(steps=0,cutbacks=0,max_mass_relative_error=0.,max_energy_relative_error=0.)
    centres,vol,_=thermal_geometry(s.liner_edges,np.ones(len(s.virgin)))
    f=solve_face(cfg['initial_temperature_C'],s.virgin[0]/vol[0],0.,w.inner,centres[0],0.,cfg)
    def sample(face_C,interface_C,outer_C,speed,phase):
        return {**nominal.point(w,s,face_C,interface_C,outer_C,speed,totals),**phase}
    history=[sample(f.temperature_C,s.case_C[0],s.case_C[-1],0.,w.phase(s.case_C))]
    profiles=[nominal.profile(w,s)]
    if cp_path.exists():
        cp=json.loads(cp_path.read_text())
        assert cp['plan_sha256']==sha and cp['tag']==tag
        s=nominal.decode(cp['state'])
        totals,events,stats,history,profiles=(cp[k] for k in ('ledger','events','stats','history','profiles'))
    def checkpoint(status):
        host_check()
        atomic(cp_path,dict(plan_sha256=sha,tag=tag,state=nominal.encode(s),ledger=totals,events=events,
                            stats=stats,history=history,profiles=profiles))
        atomic(work/'status.json',dict(utc=utc(),tag=tag,time_s=s.time,status=status,events=events))
    checkpoint('RUNNING')
    last=time.monotonic()
    horizon=plan['horizon_s']
    targets=sorted(set(np.arange(.5,horizon,.5).tolist()+[.00625,.0125,.025,.05,.1,.2,horizon]+
                       [t for t in plan['profile_times_s'] if 0<t<=horizon]))
    while s.time<horizon-1e-10 and len(s.virgin):
        if stats['steps']%128==0: host_check()
        if nominal.STOP or (pause_after is not None and stats['steps']>=pause_after):
            checkpoint('PAUSED')
            return False
        target=targets[bisect.bisect_right(targets,s.time+1e-10)]
        old=s.time
        a=w.advance(s,min(item['dt'],target-old))
        s=a.state
        for k in totals: totals[k]+=getattr(a,k)
        stats['steps']+=1
        stats['cutbacks']+=a.cutbacks
        m,h=w.inventory(s)
        mass=abs(m-m0+sum(totals[k] for k in nominal.FLOWS[:3]))/m0
        thermal=abs(h-h0-totals['film_heat']-totals['radiation_heat']+sum(totals[k] for k in nominal.FLOWS[5:10]))
        thermal/=max(1.,abs(h0),abs(totals['film_heat'])+abs(totals['radiation_heat']))
        if mass>1e-8 or thermal>1e-6: raise RuntimeError(f'Open-system balance failed: {mass}, {thermal}')
        stats['max_mass_relative_error']=max(stats['max_mass_relative_error'],mass)
        stats['max_energy_relative_error']=max(stats['max_energy_relative_error'],thermal)
        phase=w.phase(s.case_C)
        crossed=False
        conditions=(a.case_interface_C>=cfg['case_property_limit_C'],phase['max_cell_liquid']>0.,
                    phase['min_cell_liquid']>=1.,len(s.char)==0)
        for name,condition in zip(MILESTONES,conditions):
            if condition and events[name] is None:
                events[name]=[old,s.time]
                crossed=True
        if crossed or abs(target-s.time)<1e-10:
            history.append(sample(a.face_C,a.case_interface_C,a.outer_C,a.speed,phase))
        if crossed or any(abs(s.time-p)<1e-10 for p in plan['profile_times_s']):
            profiles.append(nominal.profile(w,s))
        if time.monotonic()-last>15:
            disks()
            checkpoint('RUNNING')
            last=time.monotonic()
    status='SURROGATE_EXHAUSTION' if events['exhaustion'] else 'HORIZON_WITH_LINER'
    checkpoint(status)
    atomic(record,dict(tag=tag,plan_sha256=sha,checkpoint_sha256=digest(cp_path),status=status,events=events,
        event_bracket_s=events['exhaustion'],scope_bracket_s=events['property_flag'],stats=stats,history=history,
        profiles=profiles,eligible_for_motor_lifetime=False,method='Independent retained Al thermal backing with fusion'))
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('prepare','run'))
    args=parser.parse_args()
    if args.action=='prepare':
        prepare()
        return
    disks()
    plan=json.loads(PLAN.read_text())
    sha=digest(PLAN)
    assert plan['sources']==sources() and plan['parent_sha256']==digest(nominal.PLAN) and plan['coupon_sha256']==digest(COUPON)
    with (nominal.SHARED/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,nominal.stop_signal)
        atomic(WORK/'worker.json',dict(pid=os.getpid(),started_utc=utc(),plan_sha256=sha))
        try:
            for item in plan['cases']:
                if not run_case(item,plan,sha,WORK,OUT): return
        except StorageLimitError as exc:
            stop_runs(str(exc))
            raise
        except Exception as exc:
            host_check()
            atomic(WORK/'error.json',dict(tag=item['tag'],utc=utc(),error=repr(exc)))
            raise
        atomic(WORK/'complete.json',dict(utc=utc(),cases=len(plan['cases']),plan_sha256=sha))


if __name__=='__main__': main()

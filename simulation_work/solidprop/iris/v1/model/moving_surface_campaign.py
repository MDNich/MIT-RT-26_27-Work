"""Sealed independent campaign for the coupled moving wall. No native dispatch."""
import argparse
import bisect
from dataclasses import asdict
import fcntl
import json
import os
import signal
import time
from pathlib import Path

import numpy as np

from continuous_heating_campaign import PLAN as PARENT, WORK as SHARED, digest
from moving_surface_boundary import solve_face
from moving_surface_conduction import thermal_geometry
from moving_surface_thermochemistry import recover_temperature
from moving_surface_transient import Wall, State
from ops import ROOT, TMP, StorageLimitError, atomic, disks, host_check, stop_runs, utc

PLAN = ROOT/'configs/moving_surface_campaign.json'
WORK = TMP/'moving_surface_campaign'
OUT = ROOT/'validation/moving_surface_cases'
VERIFICATION = ROOT/'validation/moving_surface_transient_verification.json'
FLOWS = ('bulk_gas','face_gas','char_products','film_heat','radiation_heat','outer_loss',
         'bulk_reaction','bulk_gas_heat','face_reaction','face_products_heat','swept_enthalpy')
STOP = False


def sources():
    names = ['moving_surface_campaign','moving_surface_transient','moving_surface_conduction',
             'moving_surface_boundary','moving_surface_thermochemistry','moving_surface_remap',
             'continuous_heating_campaign','radial_model','coupler','ops']
    return {name:digest(ROOT/f'model/{name}.py') for name in names}


def prepare():
    disks()
    if PLAN.exists():
        raise FileExistsError('Existing moving-wall campaign is immutable')
    check = json.loads(VERIFICATION.read_text())
    assert check['passed'] and check['plan_sha256'] == digest(PARENT)
    for name,sha in check['sources'].items():
        assert digest(ROOT/f'model/{name}.py') == sha
    parent = json.loads(PARENT.read_text())
    cases = []
    for n,dt,label in [(160,.08,'time08'),(160,.04,'time04'),(320,.04,'time04'),
                       (640,.04,'time04'),(640,.02,'time02')]:
        for row in parent['cases']:
            cases.append(dict(case=row['case'],tag=f"{row['case']}_moving{n}_{label}",
                              n=n,nc=n//4,dt=dt,configuration=row['configuration']))
    atomic(PLAN,dict(created_utc=utc(),method='Independent moving finite volumes',
                     verification_sha256=digest(VERIFICATION),parent_plan_sha256=digest(PARENT),
                     sources=sources(),cases=cases,horizon_s=960.,
                     description='Five settings per motor, isolating fixed-mesh time and fixed-step spatial changes. '
                        'Heat from ignition is continuous; record the first provisional casing-property flag '
                        'and continue with the inherited intact surrogate. No motor-lifetime qualification.',
                     profile_times_s=[0.,1.,7.,30.,60.,90.,120.,150.,240.,480.,960.]))


def encode(s):
    return {k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in asdict(s).items()}


def decode(d):
    return State(**{k:v if k=='time' else np.asarray(v,dtype=float) for k,v in d.items()})


def profile(w,s):
    edges = s.liner_edges
    return dict(time_s=s.time,liner_edges_m=edges.tolist(),
                liner_temperature_C=recover_temperature(s.virgin,s.char,s.enthalpy).tolist(),
                liner_virgin_kg_per_rad_m=s.virgin.tolist(),liner_char_kg_per_rad_m=s.char.tolist(),
                casing_edges_m=w.case_edges.tolist(),casing_cell_C=s.case_C.tolist())


def point(w,s,face,interface,outer,speed,totals):
    m,h = w.inventory(s)
    return dict(time_s=s.time,remaining_mm=1000.*(w.interface-s.liner_edges[0]),
                face_C=face,interface_C=interface,outer_C=outer,speed_m_s=speed,
                virgin_kg_per_rad_m=float(sum(s.virgin)),char_kg_per_rad_m=float(sum(s.char)),
                solid_mass_kg_per_rad_m=m,solid_sensible_J_per_rad_m=h,ledger=dict(totals))


def run_case(item,plan,sha,work,out,stop_after=None):
    """One controller. stop_after is an accepted-step boundary for restart verification."""
    disks()
    cfg = item['configuration']
    w = Wall(cfg,item['n'],item['nc'])
    tag = item['tag']
    cp_path, result = work/f'{tag}_checkpoint.json',out/f'{tag}.json'
    if result.exists():
        saved = json.loads(result.read_text())
        assert saved['plan_sha256']==sha and saved['checkpoint_sha256']==digest(cp_path)
        return True
    s = w.initial()
    m0,h0 = w.inventory(s)
    totals = dict.fromkeys(FLOWS,0.)
    centres,vol,_ = thermal_geometry(s.liner_edges,np.ones(len(s.virgin)))
    f0 = solve_face(cfg['initial_temperature_C'],s.virgin[0]/vol[0],0.,w.inner,centres[0],0.,cfg)
    history = [point(w,s,f0.temperature_C,s.case_C[0],s.case_C[-1],0.,totals)]
    profiles = [profile(w,s)]
    flag = event = None
    stats = dict(steps=0,cutbacks=0,max_iterations=0,min_step_s=None,max_step_s=0.,
                 max_mass_relative_error=0.,max_energy_relative_error=0.,max_step_energy_error_J_per_rad_m=0.)
    if cp_path.exists():
        cp = json.loads(cp_path.read_text())
        assert cp['plan_sha256']==sha and cp['tag']==tag
        s,totals,stats = decode(cp['state']),cp['ledger'],cp['stats']
        history,profiles = cp['history'],cp['profiles']
        flag,event = cp['scope_bracket_s'],cp['event_bracket_s']
    horizon = plan['horizon_s']
    ticks = np.arange(.5,horizon,.5)
    targets = sorted(set(ticks.tolist()+[t for t in (.00625,.0125,.025,.05,.1,.2,horizon,*plan['profile_times_s']) if 0<t<=horizon]))
    def checkpoint(status):
        host_check()
        atomic(cp_path,dict(plan_sha256=sha,tag=tag,state=encode(s),ledger=totals,stats=stats,
                            history=history,profiles=profiles,scope_bracket_s=flag,event_bracket_s=event))
        atomic(work/'status.json',dict(utc=utc(),tag=tag,status=status,time_s=s.time,
                                      remaining_mm=1000.*(w.interface-s.liner_edges[0]),steps=stats['steps'],
                                      first_property_crossing_s=flag,model_exhaustion_s=event))
    checkpoint('RUNNING')
    last_write = time.monotonic()
    while s.time < horizon-1e-10 and len(s.virgin):
        if stats['steps']%128==0: host_check()
        if STOP or (stop_after is not None and stats['steps']>=stop_after):
            checkpoint('PAUSED')
            return False
        target = targets[bisect.bisect_right(targets,s.time+1e-10)]
        old_t = s.time
        a = w.advance(s,min(item['dt'],target-s.time))
        s = a.state
        for key in FLOWS: totals[key] += getattr(a,key)
        stats['steps'] += 1
        stats['cutbacks'] += a.cutbacks
        stats['min_step_s'] = min(stats['min_step_s'] or a.dt,a.dt)
        stats['max_step_s'] = max(stats['max_step_s'],a.dt)
        stats['max_iterations'] = max(stats['max_iterations'],a.iterations)
        stats['max_step_energy_error_J_per_rad_m'] = max(stats['max_step_energy_error_J_per_rad_m'],abs(a.energy_error))
        m,h = w.inventory(s)
        mass = abs(m-m0+sum(totals[k] for k in FLOWS[:3]))/m0
        energy = abs(h-h0-totals['film_heat']-totals['radiation_heat']+sum(totals[k] for k in FLOWS[5:10]))
        energy /= max(1.,abs(h0),abs(totals['film_heat'])+abs(totals['radiation_heat']))
        stats['max_mass_relative_error'] = max(stats['max_mass_relative_error'],mass)
        stats['max_energy_relative_error'] = max(stats['max_energy_relative_error'],energy)
        if mass>1e-8 or energy>1e-6:
            raise RuntimeError(f'Open system balance failed at {s.time}: {mass}, {energy}')
        crossed = flag is None and a.case_interface_C >= cfg['case_property_limit_C']
        if crossed: flag = [old_t,s.time]
        if not len(s.virgin): event = [old_t,s.time]
        if abs(s.time-target)<1e-10 or crossed or event:
            history.append(point(w,s,a.face_C,a.case_interface_C,a.outer_C,a.speed,totals))
        if event or any(abs(s.time-t)<1e-10 for t in plan['profile_times_s']):
            profiles.append(profile(w,s))
        if time.monotonic()-last_write > 15:
            disks()
            checkpoint('RUNNING')
            last_write = time.monotonic()
    status = 'SURROGATE_EXHAUSTION' if event else 'HORIZON_WITH_LINER'
    checkpoint(status)
    atomic(result,dict(tag=tag,plan_sha256=sha,checkpoint_sha256=digest(cp_path),status=status,stats=stats,
                       history=history,profiles=profiles,scope_bracket_s=flag,event_bracket_s=event,
                       post_scope=flag is not None,eligible_for_motor_lifetime=False,
                       method='Independent coupled moving-wall finite volumes, prescribed continuous gas exposure.'))
    return True


def stop_signal(_signum,_frame):
    global STOP
    STOP = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','run'])
    args = parser.parse_args()
    if args.action=='prepare':
        prepare()
        return
    disks()
    plan = json.loads(PLAN.read_text())
    sha = digest(PLAN)
    assert sources()==plan['sources'] and digest(PARENT)==plan['parent_plan_sha256']
    assert digest(VERIFICATION)==plan['verification_sha256']
    with (SHARED/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,stop_signal)
        atomic(WORK/'worker.json',dict(pid=os.getpid(),plan_sha256=sha,started_utc=utc()))
        try:
            for item in plan['cases']:
                if not run_case(item,plan,sha,WORK,OUT): return
        except StorageLimitError as exc:
            stop_runs(str(exc))
            raise
        except Exception as exc:
            host_check()
            atomic(WORK/'error.json',dict(tag=item['tag'],error=repr(exc),utc=utc()))
            raise
        atomic(WORK/'complete.json',dict(plan_sha256=sha,cases=len(plan['cases']),utc=utc()))


if __name__ == '__main__':
    main()

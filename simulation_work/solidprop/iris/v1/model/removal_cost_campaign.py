"""Vary only the char-removal energy, allowing both backing materials to evolve."""
import argparse
from copy import deepcopy
import fcntl
import os
import signal
import time


from audit_backing_film import meets
from audit_liner_energy import analyze
from audit_moving_surface import compare
from backing_film_campaign import inputs, parents, MATERIALS, read
from continuous_heating_campaign import digest
from moving_surface_campaign import SHARED, stop_signal
from ops import ROOT, TMP, StorageLimitError, atomic, disks, host_check, stop_runs, utc
from sector_exposure import balances, integrate
from sector_wall import banded

PLAN=ROOT/'configs/evolving_removal_cost.json'
WORK=TMP/'evolving_removal_cost'
OUT=ROOT/'validation/evolving_removal_cost.json'


def prepare():
    disks()
    if PLAN.exists(): raise FileExistsError(PLAN)
    previous=read(ROOT/'configs/moving_surface_sensitivities.json')
    jobs=[]
    for name,parent in parents().items():
        for cost in (17.5,70.):
            source=next(row for row in previous['cases'] if row['case']==name and row['scenario']==f'cost{cost:g}')
            actual=source['configuration']['char_law']['effective_endothermic_cost_J_kg']
            assert actual==cost*1e6 and parent['configuration']['char_law']['effective_endothermic_cost_J_kg']==35e6
            jobs.append(dict(case=name,parent_tag=parent['tag'],cost_J_kg=actual))
    fingerprint=inputs()
    for mod in ('removal_cost_campaign','audit_moving_surface','audit_liner_energy','audit_backing_film','sector_exposure','sector_wall'):
        p=ROOT/f'model/{mod}.py'
        fingerprint[str(p.relative_to(ROOT))]=digest(p)
    atomic(PLAN,dict(inputs=fingerprint,jobs=jobs,horizon_s=360.,profile_times_s=[0.,1.,7.,30.,60.,90.,120.,180.,240.,360.],
        levels={'mesh':[320,80,.04],'time':[640,160,.04],'fine':[640,160,.02]},
        followups={'mesh':[[1280,320,.04],[2560,640,.04]],'time':[[640,160,.01],[640,160,.005],[640,160,.0025]]},
        fem=[160,40,.02],limits={'FV_event_relative':.05,'FV_bracket_overlap':True,'FV_vs_FE_event_relative':.01,
        'thickness_mm':.02,'thickness_fraction':.01,'mass_relative':1e-8,'energy_relative':1e-6},
        scope='Assumption sensitivity only. Change the specified cost per kg of removed char while keeping nominal heating and kinetics.'))


def run():
    disks()
    plan=read(PLAN); signature=digest(PLAN)
    assert all(digest(ROOT/p)==v for p,v in plan['inputs'].items())
    if (WORK/'complete.json').exists():
        done=read(WORK/'complete.json')
        assert done['plan_sha256']==signature and done['audit_sha256']==digest(OUT)
        return
    refs=parents()
    work=WORK/'cases';work.mkdir(parents=True,exist_ok=True)
    results={}
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,stop_signal)
    last_check=0.
    def guard():
        nonlocal last_check
        host_check()
        if time.monotonic()-last_check>15:
            disks();last_check=time.monotonic()
    atomic(WORK/'worker.json',dict(pid=os.getpid(),plan_sha256=signature,utc=utc()))
    for job in plan['jobs']:
        name=job['case'];parent=refs[name];cost=job['cost_J_kg']
        assert parent['tag']==job['parent_tag']
        cfg=deepcopy(parent['configuration'])
        cfg['char_law']['effective_endothermic_cost_J_kg']=cost
        prefix=f"{name}_cost{cost/1e6:g}"
        module=MATERIALS[cfg['case_material']]
        records={}
        def solve_fv(level):
            guard()
            n,nc,dt=level
            tag=f'{prefix}_n{n}_us{round(dt*1e6)}'
            item=dict(tag=tag,configuration=cfg,n=n,nc=nc,dt=dt)
            if not module.run_case(item,plan,signature,WORK,work): raise InterruptedError('FV checkpoint saved')
            path=work/(tag+'.json')
            rec=read(path)
            cp=WORK/(tag+'_checkpoint.json')
            assert rec['tag']==tag and rec['plan_sha256']==signature and rec['checkpoint_sha256']==digest(cp)
            assert rec['status']=='SURROGATE_EXHAUSTION' and rec['eligible_for_motor_lifetime'] is False
            assert rec['stats']['max_mass_relative_error']<1e-8 and rec['stats']['max_energy_relative_error']<1e-6
            assert rec['history'][0]['time_s']==0 and rec['history'][-1]['remaining_mm']==0
            assert rec['scope_bracket_s'][1]<rec['event_bracket_s'][0]
            records[tag]=dict(sha256=digest(path),bracket_s=rec['event_bracket_s'],checkpoint_sha256=digest(cp))
            return rec
        group={k:solve_fv(v) for k,v in plan['levels'].items()}
        best=group['fine']; gates={}
        for axis,a,b in [('mesh',group['mesh'],group['time']),('time',group['time'],group['fine'])]:
            pair=compare(a,b)
            chain=[dict(tag=b['tag'],comparison=pair)]
            for level in plan['followups'][axis]:
                if meets(pair): break
                a,b=b,solve_fv(level)
                pair=compare(a,b)
                chain.append(dict(tag=b['tag'],comparison=pair))
                if axis=='time': best=b
            gates[axis]=dict(passed=meets(pair),chain=chain)
        n,nc,dt=plan['fem']
        settings=dict(n=n,nc=nc,dt_s=dt,configuration=cfg,horizon_s=plan['horizon_s'])
        ref_path=work/(prefix+'_fe.json')
        if ref_path.exists():
            saved=read(ref_path)
            assert saved['settings']==settings and saved['plan_sha256']==signature
            fe=saved['record']
        else:
            fe=integrate(settings,banded,guard)
            atomic(ref_path,dict(settings=settings,plan_sha256=signature,record=fe))
        err=balances(settings,fe)
        assert max(map(abs,err.values()))<1e-7 and fe['state']['virgin']==[]
        end=best['event_bracket_s'][1]
        history={round(r['time_s'],8):r for r in best['history']}
        common=[(a,history[round(a['time_s'],8)]) for a in fe['stats']['samples'] if round(a['time_s'],8) in history]
        assert len(common)>=int(2*min(end,fe['state']['time']))-1
        delta=max(abs(a['remaining_mm']-b['remaining_mm']) for a,b in common)
        thickness_limit=max(.02,.01*best['history'][0]['remaining_mm'])
        energy=analyze(best,settings,fe)
        accepted=(all(x['passed'] for x in gates.values()) and abs(fe['state']['time']/end-1)<.01 and delta<=thickness_limit)
        results[prefix]=dict(case=name,cost_J_kg=cost,numerical_checks_passed=bool(accepted),reported_tag=best['tag'],
                             event_s=end,events=best['events'],FV_gates=gates,FV_records=records,FE_event_s=fe['state']['time'],
                             FE_evidence_sha256=digest(ref_path),FE_balances=err,max_common_thickness_mm=delta,energy=energy)
        print(prefix,round(end,3),accepted,flush=True)
    atomic(OUT,dict(plan_sha256=signature,cases=results,native=False,eligible_for_motor_lifetime=False,
                    all_numerical_checks_passed=all(r['numerical_checks_passed'] for r in results.values())))
    atomic(WORK/'complete.json',dict(utc=utc(),plan_sha256=signature,audit_sha256=digest(OUT)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    try:
        if parser.parse_args().action=='prepare': prepare()
        else:
            with (SHARED/'worker.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                run()
    except StorageLimitError as exc:
        stop_runs(str(exc))
        raise

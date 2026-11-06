"""Verify sustained film scenarios against saved fields, step ledgers, refinement and a second solver."""
import fcntl
import json
import time
from pathlib import Path

import numpy as np

from aluminium_phase_enthalpy import caloric,equilibrium
from audit_moving_surface import compare
import backing_film_campaign as study
from cf_backing_response import CHI,DENSITY_LOSS,VIRGIN_DENSITY,mixture
from continuous_heating_campaign import digest
from moving_surface_thermochemistry import sensible
from ops import ROOT,TMP,StorageLimitError,atomic,disks,host_check,stop_runs,utc
from sector_exposure import balances,integrate
from sector_wall import banded


def audit_record(job,config,plan,plan_sha):
    tag=job['tag']
    saved=study.DATA/(tag+'.json')
    check=study.WORK/(tag+'_checkpoint.json')
    rec,cp=map(study.read,(saved,check))
    assert rec['tag']==cp['tag']==tag and rec['plan_sha256']==cp['plan_sha256']==plan_sha
    assert rec['checkpoint_sha256']==digest(check) and not rec['eligible_for_motor_lifetime']
    assert rec['status']=='SURROGATE_EXHAUSTION'
    assert all(cp[k]==rec[k] for k in ['events','stats','history','profiles'])
    rows=rec['history']
    times=np.array([r['time_s'] for r in rows])
    geo=config['geometry']
    ri,interface,outer=(geo[k] for k in ['inner_radius_m','phenolic_outer_radius_m','outer_radius_m'])
    assert times[0]==0 and np.all(np.diff(times)>0) and times[-1]==cp['state']['time']<=plan['horizon_s']
    assert np.max(np.diff([r['remaining_mm'] for r in rows]))<=1e-9
    assert abs(rows[0]['remaining_mm']-1000*(interface-ri))<1e-10 and rows[-1]['remaining_mm']==0
    assert all(min(abs(times-t))<1e-8 for t in np.arange(.5,times[-1],.5))
    assert rec['event_bracket_s']==rec['events']['exhaustion'] and rec['scope_bracket_s']==rec['events']['property_flag']
    cf=config['case_material']=='cf'
    checks=dict(property_flag=lambda r:r['interface_C']>=config['case_property_limit_C'],exhaustion=lambda r:r['remaining_mm']==0)
    if cf:
        checks.update(inner_pool_half=lambda r:r['inner_pool']>=.5,outer_pool_half=lambda r:r['outer_pool']>=.5,
                      first_1000C=lambda r:r['max_backing_C']>=1000.)
    else:
        checks.update(first_melt=lambda r:r['max_cell_liquid']>0,all_liquid=lambda r:r['min_cell_liquid']>=1.)
    for key,condition in checks.items():
        first=next((r for r in rows if condition(r)),None)
        span=rec['events'][key]
        if first is None: assert span is None
        else: assert span[1]==first['time_s'] and 0<span[1]-span[0]<=job['dt']+1e-9
    assert rec['events']['property_flag'][1]<rec['event_bracket_s'][0]
    liner0=config['material']['virgin_reference_density_kg_m3']*(interface-ri)*(interface+ri)/2
    case_edges=np.linspace(interface,outer,job['nc']+1)
    original=np.diff(case_edges)*(case_edges[1:]+case_edges[:-1])*.5
    original*=VIRGIN_DENSITY if cf else config['material']['aluminium_density_kg_m3']
    peak_m=peak_h=0.
    for row in rows:
        led=row['ledger']
        assert np.isfinite(list(led.values())).all() and np.isfinite([v for k,v in row.items() if k!='ledger']).all()
        m=row['virgin_kg_per_rad_m']+row['char_kg_per_rad_m']+sum(led[k] for k in ('bulk_gas','face_gas','char_products'))
        error=abs(m-liner0)/liner0
        energy=(row['solid_sensible_J_per_rad_m']-rows[0]['solid_sensible_J_per_rad_m']-led['film_heat']-led['radiation_heat']
                +sum(led[k] for k in ('outer_loss','bulk_reaction','bulk_gas_heat','face_reaction','face_products_heat')))
        if cf:
            error=max(error,abs(row['backing_retained_kg_per_rad_m']+led['backing_gas']-sum(original))/sum(original))
            energy+=led['backing_gas_heat']-led['backing_reaction_heat']
        peak_m=max(peak_m,error)
        peak_h=max(peak_h,abs(energy)/max(1.,abs(led['film_heat'])+abs(led['radiation_heat'])))
    by_time={r['time_s']:r for r in rows}
    previous_paths=np.zeros((2,job['nc']))
    for prof in rec['profiles']:
        row=by_time[prof['time_s']]
        v,c,t,edge=(np.array(prof[k]) for k in ('liner_virgin_kg_per_rad_m','liner_char_kg_per_rad_m',
                                               'liner_temperature_C','liner_edges_m'))
        assert len(v)==len(c)==len(t)==len(edge)-1 and np.all(v>=0) and np.all(c>=0) and np.all(np.diff(edge)>0)
        assert edge[-1]==interface and abs(1000*(interface-edge[0])-row['remaining_mm'])<1e-9
        assert abs(sum(v)-row['virgin_kg_per_rad_m'])+abs(sum(c)-row['char_kg_per_rad_m'])<1e-10
        ht=sensible(t)
        tc=np.array(prof['casing_cell_C'])
        assert tc.shape==original.shape and np.array_equal(prof['casing_edges_m'],case_edges)
        if cf:
            paths=np.array(prof['backing_paths'])
            assert paths.shape==previous_paths.shape and np.all(paths>=previous_paths-1e-11) and max(paths.sum(axis=0))<1+1e-10
            previous_paths=paths
            extent=CHI@paths
            mass=original*(1.-DENSITY_LOSS*extent)
            hc=mixture(tc,extent)[0]
            assert abs(sum(mass)-row['backing_retained_kg_per_rad_m'])<1e-10
        else:
            mass=original
            hc=caloric(tc,config['al_fusion_width_K'])[0]
            liquid=equilibrium(hc)[1]
            assert abs(mass@liquid/sum(mass)-row['mass_fraction_liquid'])<1e-10
        assert abs(v@ht[:,0]+c@ht[:,1]+mass@hc-row['solid_sensible_J_per_rad_m'])<1e-6
    last=rec['profiles'][-1]; state=cp['state']
    assert state['liner_edges']==[interface] and state['virgin']==state['char']==state['enthalpy']==[]
    assert state['case_C']==last['casing_cell_C'] and cp['ledger']==rows[-1]['ledger'] and last['time_s']==times[-1]
    if cf: assert last['backing_paths']==cp['paths']
    assert max(peak_m,rec['stats']['max_mass_relative_error'])<plan['limits']['mass_relative']
    assert max(peak_h,rec['stats']['max_energy_relative_error'])<plan['limits']['heat_relative']
    return rec,dict(sha256=digest(saved),checkpoint_sha256=digest(check),events=rec['events'],
                    max_mass_error=peak_m,max_heat_error=peak_h)


def heat_trace(rec,config):
    """Recover mean film flux from cumulative energy and the moving cylindrical area.

    The exact area-time of any interval lies between its endpoint areas times dt.
    This gives rigorous enclosures of the area-weighted mean for positive heat.
    Keep only shared half-second stations and the final event for the plotted line.
    """
    rows=[r for r in rec['history'] if abs(r['time_s']*2-round(r['time_s']*2))<1e-8]
    if rows[-1]!=rec['history'][-1]: rows.append(rec['history'][-1])
    t=np.array([r['time_s'] for r in rows])
    r=config['geometry']['phenolic_outer_radius_m']-1e-3*np.array([s['remaining_mm'] for s in rows])
    dt=np.diff(t)
    q=np.diff([s['ledger']['film_heat'] for s in rows])/1e6
    assert np.all(q>=0) and np.all(dt>0) and np.all(np.diff(r)>=0)
    lower=r[:-1]*dt;upper=r[1:]*dt
    flux=q/(.5*(upper+lower))
    return dict(time_s=((t[1:]+t[:-1])*.5).tolist(),mean_film_MW_m2=flux.tolist(),
                total_film_MJ_per_initial_m2=sum(q)/r[0],whole_mean_bounds_MW_m2=[sum(q)/sum(upper),sum(q)/sum(lower)],
                max_interval_flux_uncertainty_MW_m2=float(max(q/lower-q/upper)),
                peak_hot_C=max(s['face_C'] for s in rec['history']),
                event_s=t[-1],events=rec['events'],initial_mm=rows[0]['remaining_mm'])


def independent_fem(cfg,case,h,reference,guard):
    setting=dict(configuration=cfg,n=160,nc=40,dt_s=.02,horizon_s=360.)
    folder=study.WORK/'finite_element_checks'
    folder.mkdir(exist_ok=True)
    path=folder/f'{case}_h{h}.json'
    check_paths=[ROOT/f'model/{name}.py' for name in ('sector_wall','sector_exposure','audit_backing_film')]
    hashes={p.name:digest(p) for p in check_paths}
    if path.exists():
        saved=study.read(path)
        assert saved['input']==setting and saved['code']==hashes
        rec=saved['state']
    else:
        rec=integrate(setting,banded,guard)
        atomic(path,dict(input=setting,code=hashes,state=rec))
    errors=balances(setting,rec)
    assert max(map(abs,errors.values()))<1e-7 and rec['state']['virgin']==[]
    cells=reference['history']
    fe=rec['stats']['samples']
    shared={round(r['time_s'],8):r for r in cells}
    pairs=[(r,shared[round(r['time_s'],8)]) for r in fe if round(r['time_s'],8) in shared]
    ends=[rec['state']['time'],cells[-1]['time_s']]
    assert len(pairs)>=int(2*min(ends))-1 and abs(ends[0]/ends[1]-1)<.01
    thickness=max(abs(a['remaining_mm']-b['remaining_mm']) for a,b in pairs)
    assert thickness<max(.02,cells[0]['remaining_mm']*.01)
    return dict(event_s=ends[0],delta_event_s=ends[0]-ends[1],max_common_thickness_mm=thickness,
                max_common_interface_K=max(abs(a['interface_C']-b['interface_C']) for a,b in pairs),
                balances=errors,record_sha256=digest(path))


def meets(pair):
    return pair['event_under_5_percent'] and pair['brackets_overlap'] and pair['thickness_pass']


def further_checks(job, config, plan, sha, group, comparisons, guard):
    """Preserve every failed pair and do isolated follow-ups with a frozen schedule.

    Every level is specified before running. Select the finest passing consecutive
    pair, without skipping an intervening disagreement. If none passes, retain
    an open gate for that coordinate.
    """
    failures=[key for key,pair in comparisons.items() if not meets(pair)]
    if not failures: return {},group['fine'],True
    levels={'mesh':[(1280,320,.04),(2560,640,.04)],
            'time':[(640,160,.01),(640,160,.005),(640,160,.0025)]}
    selected={k:levels[k] for k in failures}
    baseline_ids={k:digest(study.DATA/(job['case']+'_film'+str(job['h0'])+'_'+k+'.json')) for k in group}
    schedule=dict(case=job['case'],h0=job['h0'],parent_sha256=sha,sources=plan['inputs'],
                  initial_records=baseline_ids,coord_levels=selected,policy='Evaluate in order until a passing adjacent pair or schedule end.')
    directory=ROOT/'configs/evolving_backing_film_rechecks'
    directory.mkdir(exist_ok=True)
    path=directory/(job['case']+'_film'+str(job['h0'])+'.json')
    if not path.exists(): atomic(path,schedule)
    if study.read(path)!=json.loads(json.dumps(schedule)): raise RuntimeError('Changed refinement plan')
    extension_sha=digest(path)
    module=study.MATERIALS[config['case_material']]
    best=group['fine']; proof={}
    for axis,limits in selected.items():
        previous=group['time' if axis=='mesh' else 'fine']
        checked=[]
        for n,nc,dt in limits:
            guard()
            tag=f"{job['case']}_film{job['h0']}_{axis}_n{n}_us{round(dt*1e6)}"
            extra=dict(job,n=n,nc=nc,dt=dt,tag=tag)
            complete=module.run_case(dict(extra,configuration=config),plan,extension_sha,study.WORK,study.DATA)
            if not complete: raise InterruptedError('Refinement stopped with a saved checkpoint')
            rec,receipt=audit_record(extra,config,plan,extension_sha)
            pair=compare(previous,rec)
            checked.append(dict(level=[n,nc,dt],record=receipt,pair=pair,passed=meets(pair)))
            previous=rec
            if axis=='time': best=rec
            if meets(pair): break
        proof[axis]=dict(schedule_sha256=extension_sha,checks=checked,passed=checked[-1]['passed'])
    return proof,best,all(p['passed'] for p in proof.values())


def main():
    disks()
    plan,sha,refs=study.verified_plan()
    completion=study.read(study.WORK/'complete.json')
    assert completion['plan_sha256']==sha and completion['cases']==len(plan['cases'])
    last=0.
    def guard():
        nonlocal last
        host_check()
        if time.monotonic()-last>=15: disks();last=time.monotonic()
    results={}; traces={}
    for case,parent in refs.items():
        material=parent['configuration']['case_material']
        module=study.MATERIALS[material]
        basepath=module.OUT/(parent['tag']+'.json')
        baseline=study.read(basepath)
        oldaudit=study.read(ROOT/f"validation/{'cf' if material=='cf' else 'aluminium'}_backing_audit.json")
        orig=oldaudit['records'][parent['tag']]
        assert digest(basepath)==orig.get('sha256',orig.get('record_sha256'))
        traces[case]={'1000':heat_trace(baseline,parent['configuration'])}
        results[case]={'1000':dict(event_s=baseline['event_bracket_s'][1],sha256=digest(basepath),events=baseline['events'])}
        for h in [500,2000]:
            group={};receipts={}
            for job in (r for r in plan['cases'] if r['case']==case and r['h0']==h):
                guard()
                cfg=study.resolve(job,refs)['configuration']
                group[job['level']],receipts[job['level']]=audit_record(job,cfg,plan,sha)
            pairs={'mesh':compare(group['mesh'],group['time']),'time':compare(group['time'],group['fine'])}
            fv_ok=all(meets(p) for p in pairs.values())
            fine_job=next(row for row in plan['cases'] if row['case']==case and row['h0']==h and row['level']=='fine')
            additional,ref,final_ok=further_checks(fine_job,cfg,plan,sha,group,pairs,guard)
            item=independent_fem(cfg,case,h,ref,guard)
            traces[case][str(h)]=heat_trace(ref,cfg)
            results[case][str(h)]=dict(event_s=ref['event_bracket_s'][1],events=ref['events'],FV_records=receipts,
                                  FV_comparisons=pairs,reference_FE=item,initial_FV_pairs_pass=fv_ok,additional_FV_checks=additional,
                                  final_FV_pairs_pass=final_ok,reported_FV_tag=ref['tag'])
            print(case,h,results[case][str(h)]['event_s'],fv_ok,item['delta_event_s'],flush=True)
    trace_path=ROOT/'validation/evolving_backing_film_histories.json'
    atomic(trace_path,traces)
    atomic(study.PROOF,dict(utc=utc(),plan_sha256=sha,auditor_sha256=digest(Path(__file__)),jobs=len(plan['cases']),
                histories_sha256=digest(trace_path),results=results,native=False,eligible_for_motor_lifetime=False))


if __name__=='__main__':
    try:
        with (study.moving.SHARED/'worker.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            main()
    except StorageLimitError as exc:
        stop_runs(str(exc))
        raise

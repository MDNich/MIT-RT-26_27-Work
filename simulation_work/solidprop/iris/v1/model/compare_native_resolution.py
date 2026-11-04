"""Compare completed native resolutions without assigning results to queued runs."""
import hashlib
import json
from ops import ROOT,TMP,atomic,disks


def summary(name):
    accepted=ROOT/'validation'/f'accepted_{name}.json'
    if not accepted.exists():
        return None
    a=json.loads(accepted.read_text())
    assert a['passed']
    runtime=TMP/'runs'/name
    cfg=json.loads((runtime/'config.json').read_text())
    assert cfg['native_reaction_temperature']=='midpoint'
    assert hashlib.sha256((runtime/'config.json').read_bytes()).hexdigest()==a['config_sha256']
    history=[json.loads((runtime/'checkpoints'/f'audit_{i:06d}.json').read_text())
             for i in range(1,a['accepted_steps']+1)]
    assert history[-1]['time_s']==a['time_s']
    complete=a['status']=='COMPLETED_HORIZON'
    scope=a['status']=='CASE_PROPERTY_LIMIT_REACHED'
    comparison_path=ROOT/'validation'/f'native_pulse_comparison_{name if cfg.get("campaign_role")=="native_resolution" else cfg["case_id"]}.json'
    if not comparison_path.exists():
        return None
    comparison=json.loads(comparison_path.read_text())
    assert comparison['runtime']==name and comparison['comparison_passed']
    assert comparison['accepted_native_index']==a['accepted_steps']
    peaks={}
    for key in ['case_inner_max_C','case_outer_max_C']:
        h=max(history,key=lambda d:d[key])
        peaks[key]=dict(temperature_C=h[key],time_s=h['time_s'])
    return dict(runtime=name,case=cfg['case_id'],phenolic_cells=cfg['geometry']['phenolic_radial_rows'],
        case_cells=cfg['geometry']['aluminium_radial_rows'],through_s=a['time_s'],status=a['status'],
        complete=complete,scope_limited=scope,
        scope_bracket_s=[history[-1]['time_s']-history[-1]['dt_s'],history[-1]['time_s']] if scope else None,
        sampled_maxima=peaks,remaining_mm=1000*history[-1]['phenolic_remaining_thickness_m'],
        initial_phenolic_mm=1000*cfg['geometry']['phenolic_thickness_m'],
        config_sha256=a['config_sha256'],accepted_record_sha256=hashlib.sha256(accepted.read_bytes()).hexdigest(),
        independent_comparison_sha256=hashlib.sha256(comparison_path.read_bytes()).hexdigest())


def main():
    disks()
    plan=json.loads((ROOT/'validation/native_resolution_plan.json').read_text())
    records={};checks=[];pending=[]
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        names={'primary':f'{case}_pulse7_n80_midpoint_tight'}
        names.update({r['level']:r['runtime'] for r in plan['cases'] if r['case']==case})
        for name in names.values():
            d=summary(name)
            if d:records[name]=d
            else:pending.append(name)
        pairs=[('primary','time_quarter'),('time_quarter','space160'),('space160','joint320')]
        if case=='sustainer_cf':pairs.append(('joint320','joint640'))
        for coarse,fine in pairs:
            if names[coarse] not in records or names[fine] not in records:continue
            a,b=records[names[coarse]],records[names[fine]]
            full=a['complete'] and b['complete'] and abs(a['through_s']-b['through_s'])<1e-8
            censored=a['scope_limited'] and b['scope_limited']
            peak_diff={k:b['sampled_maxima'][k]['temperature_C']-a['sampled_maxima'][k]['temperature_C']
                       for k in a['sampled_maxima']} if full else None
            time_change=abs(b['scope_bracket_s'][1]/a['scope_bracket_s'][1]-1) if censored else None
            thickness=abs(b['remaining_mm']-a['remaining_mm'])
            target=max(.02,.01*a['initial_phenolic_mm'])
            passed=thickness<=target and ((full and max(map(abs,peak_diff.values()))<5) or (censored and time_change<.05))
            checks.append(dict(case=case,coarse=a['runtime'],fine=b['runtime'],passed=passed,
                complete_histories=full,both_scope_limited=censored,peak_differences_K=peak_diff,
                scope_time_relative_change=time_change,remaining_difference_mm=thickness,remaining_target_mm=target))
    atomic(ROOT/'validation/native_resolution_comparison.json',dict(complete=not pending,
        records=records,comparisons=checks,pending=pending,
        qualification='Completed native ANSYS comparisons only. Intermediate mesh failures remain visible even if the final refinement passes. Property-scope timing is not casing failure or burnthrough.'))
    print('Completed native records:',len(records),'comparisons:',len(checks),'pending:',len(pending))


if __name__=='__main__':
    main()

"""Independent combined-input seven-second pulse checks; never motor lifetimes."""
import copy
import fcntl
import hashlib
import json
from pathlib import Path
from radial_model import RadialModel
from ops import ROOT,TMP,atomic,disks,host_check,utc

CASES=['sustainer_al','sustainer_cf','booster_al','booster_cf']
SCENARIOS={
    'heating_transport':dict(heating={'h0_W_m2_K':2000.},
        material={'phenolic_k_scale':1.2,'phenolic_cp_scale':.8}),
    'heating_consumption':dict(heating={'h0_W_m2_K':2000.},
        material={'phenolic_k_scale':.8},
        char_law={'effective_endothermic_cost_J_kg':17.5e6})}
LEVELS=[('n80',80,20,.003125,.0625),
        ('n160',160,40,.00078125,.015625),
        ('n320',320,80,.0001953125,.00390625)]


def run_one(case,scenario,level):
    tag,nph,ncase,dt,post=level
    source=ROOT/'configs'/f'{case}_pulse7_n80_midpoint_tight.json'
    cfg=json.loads(source.read_text())
    for section,values in SCENARIOS[scenario].items():cfg[section].update(values)
    cfg['geometry'].update(phenolic_radial_rows=nph,aluminium_radial_rows=ncase)
    cfg.update(macro_dt_s=dt,post_pulse_macro_dt_s=post,post_pulse_initial_dt_s=5*dt)
    cfg['provenance']['combined_sensitivity']=(
        'Joint engineering perturbation drawn from the earlier one-at-a-time screen. '
        'Not measured uncertainty, statistical confidence or a proven worst case.')
    source_bytes=(ROOT/'model/radial_model.py').read_bytes()
    sha=hashlib.sha256(source_bytes).hexdigest()
    cfg_sha=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    target=ROOT/'validation/radial'/f'{case}_combined_pulse7_{scenario}_{tag}.json'
    if target.exists():
        d=json.loads(target.read_text())
        assert d['model_sha256']==sha and d['configuration_sha256']==cfg_sha
        return d
    host_check()
    atomic(TMP/'combined_sensitivity_progress.json',dict(utc=utc(),case=case,scenario=scenario,
        level=tag,status='RUNNING',native=False))
    archive=ROOT/'validation/source_archive'/f'radial_model_{sha}.py'
    if not archive.exists():archive.write_bytes(source_bytes)
    model=RadialModel(cfg)
    state,history,_=model.run(cfg['end_time_s'],dt=dt,post_dt=post,record_dt=.1,
        targets=[7.],check=host_check,stop_at_property_limit=True)
    peaks={k:max(history,key=lambda h:h[k]) for k in ['interface_C','outer_C']}
    result=dict(method='Independent radial finite elements, NOT native ANSYS',case=case,
        scenario=scenario,level=tag,configuration=cfg,configuration_sha256=cfg_sha,
        model_sha256=sha,parent_configuration_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        eligible_for_motor_lifetime=False,
        qualification='Combined hypothetical seven-second pulse. Property flag is model scope, not failure. Engineering perturbations are not uncertainty bounds.',
        final=history[-1],history=history,event_bracket_s=model.event_bracket,
        property_limit_bracket_s=model.property_bracket,
        sampled_maxima={k:dict(temperature_C=v[k],time_s=v['time_s']) for k,v in peaks.items()},
        max_energy_relative_error=model.max_energy_error,max_mass_relative_error=model.max_mass_error,
        max_retained_char_fraction_of_initial_mass=model.max_retained_fraction,steps=model.steps)
    atomic(target,result)
    print(case,scenario,tag,result['final'],flush=True)
    return result


def compare(a,b):
    full=not any(x['property_limit_bracket_s'] or x['event_bracket_s'] for x in [a,b]) and abs(a['final']['time_s']-b['final']['time_s'])<1e-8
    scope=bool(a['property_limit_bracket_s'] and b['property_limit_bracket_s'])
    peak_diff={k:b['sampled_maxima'][k]['temperature_C']-a['sampled_maxima'][k]['temperature_C']
        for k in a['sampled_maxima']} if full else None
    timing=abs(b['property_limit_bracket_s'][1]/a['property_limit_bracket_s'][1]-1) if scope else None
    thickness=abs(b['final']['remaining_mm']-a['final']['remaining_mm'])
    tolerance=max(.02,10*a['configuration']['geometry']['phenolic_thickness_m'])
    passed=thickness<=tolerance and ((full and max(map(abs,peak_diff.values()))<5) or (scope and timing<.05))
    return dict(case=a['case'],scenario=a['scenario'],coarse=a['level'],fine=b['level'],
        complete_histories=full,both_scope_limited=scope,scope_time_relative_change=timing,
        peak_differences_K=peak_diff,remaining_difference_mm=thickness,remaining_target_mm=tolerance,
        passed=passed,exhaustion_excluded=bool(a['event_bracket_s'] or b['event_bracket_s']))


def main():
    disks()
    # One background independent worker; never create another native queue.
    with open(TMP/'combined_sensitivity.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        records={};comparisons=[]
        # Finish each mesh level across all scenarios before finer calculations.
        for level in LEVELS:
            for case in CASES:
                for scenario in SCENARIOS:
                    d=run_one(case,scenario,level)
                    records[(case,scenario,level[0])]=d
                    if level[0]!='n80':
                        previous='n80' if level[0]=='n160' else 'n160'
                        comparisons.append(compare(records[(case,scenario,previous)],d))
                    atomic(ROOT/'validation/combined_pulse_sensitivity.json',dict(
                        complete=len(records)==24,independent_only=True,completed_runs=len(records),
                        planned_runs=24,comparisons=comparisons,
                        scenarios=SCENARIOS,
                        qualification='Joint engineering scenarios, not inferred firing conditions or confidence bounds. Native confirmation remains pending. Failing refinement comparisons must be resolved before interpreting a combined response.'))
        atomic(TMP/'combined_sensitivity_progress.json',dict(utc=utc(),status='COMPLETE',native=False))


if __name__=='__main__':
    main()

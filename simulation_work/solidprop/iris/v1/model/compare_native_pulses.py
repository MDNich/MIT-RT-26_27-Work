"""Compare immutable accepted native pulse states with an independent assembly."""
import gzip
import hashlib
import json
import math
import numpy as np
from radial_model import RadialModel
from ops import ROOT,TMP,atomic,disks,host_check


def compare(name):
    run=TMP/'runs'/name
    if not (run/'state.json').exists():return
    terminal=json.loads((run/'state.json').read_text())
    if terminal['index']<1:return
    cfg=json.loads((run/'config.json').read_text());g=cfg['geometry']
    audits={int(p.stem.split('_')[1]):json.loads(p.read_text()) for p in sorted((run/'checkpoints').glob('audit_*.json')) if int(p.stem.split('_')[1])<=terminal['index']}
    indices={terminal['index']}
    for t in [.1,1,2,5,7,10,20,30,60,90,127,150,200,250,300]:
        found=[i for i,a in audits.items() if abs(a['time_s']-t)<1e-8]
        indices.update(found)
    # Check the last old-face solve and first new-face solve explicitly.
    for i,a in audits.items():
        if a['elements_scheduled_for_removal']:
            indices.add(i)
            if i+1 in audits:indices.add(i+1)
    targets=sorted(audits[i]['time_s'] for i in indices)
    model=RadialModel(cfg)
    _,reference_history,snaps=model.run(targets[-1],dt=cfg['macro_dt_s'],post_dt=cfg.get('post_pulse_macro_dt_s'),targets=targets,check=host_check,stop_at_property_limit=False)
    plane=(g['angular_divisions']+1)*(g['axial_divisions']+1);nf=g['faces_per_row']
    scale=math.radians(g['angle_deg'])*g['length_m'];comparisons=[]
    for index in sorted(indices):
        a=audits[index];path=run/'checkpoints'/f'state_{index:06d}.json.gz'
        with gzip.open(path,'rt') as f:native=json.load(f)
        s=snaps[a['time_s']]
        T=np.array([np.mean([native['temperatures'][str(1+j*plane+i)] for i in range(plane)]) for j in range(len(model.r))])
        alpha=np.array([np.mean([native['alpha'].get(str(1+j*nf+i),0.) for i in range(nf)]) for j in range(model.np)])
        common=max(native['layer'],s.layer)
        delta=s.T[common:]-T[common:]
        native_mass=native['mass_initial_kg']-native['gas_cumulative_kg']-native['char_cumulative_kg']-native['residual_ejected_kg']
        radial_mass=model.summary(s)['solid_remaining_kg_per_rad_m']*scale
        comparisons.append(dict(index=index,time_s=a['time_s'],
            max_live_profile_difference_K=float(np.max(np.abs(delta))),
            case_inner_difference_K=float(s.T[model.np]-T[model.np]),case_outer_difference_K=float(s.T[-1]-T[-1]),
            max_live_conversion_difference=float(np.max(np.abs(s.alpha.mean(axis=1)[common:]-alpha[common:]))),
            native_rows_removed_during_solve=a['rows_removed'],native_rows_scheduled=native['layer'],independent_rows_scheduled=s.layer,
            solid_mass_difference_fraction_initial=float((radial_mass-native_mass)/native['mass_initial_kg']),
            native_state_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            radius_m=model.r.tolist(),native_temperature_C=T.tolist(),independent_temperature_C=s.T.tolist(),
            native_mean_conversion=alpha.tolist(),independent_mean_conversion=s.alpha.mean(axis=1).tolist()))
    reference_events={}
    prior_layer=0
    for a in reference_history:
        if a['layer']>prior_layer:reference_events[a['layer']]=a['time_s']
        prior_layer=a['layer']
    events=[]
    for i,a in audits.items():
        if not a['elements_scheduled_for_removal']:continue
        after=audits.get(i+1)
        transfer=None
        if after:
            expected_radius=g['inner_radius_m']+a['rows_scheduled']*g['phenolic_thickness_m']/g['phenolic_radial_rows']
            transfer=bool(after['rows_removed']==a['rows_scheduled'] and abs(after['hot_radius_m']-expected_radius)<1e-12 and after['hot_power_relative_error']<=cfg['numerics']['hot_power_relative_tolerance'])
        reference_time=reference_events.get(a['rows_scheduled'])
        events.append(dict(scheduled_index=i,scheduled_time_s=a['time_s'],rows_scheduled=a['rows_scheduled'],
            native_event_bracket_s=[audits[i-1]['time_s'] if i>1 else 0.,a['time_s']],
            independent_scheduled_time_s=reference_time,
            scheduled_time_difference_s=reference_time-a['time_s'] if reference_time is not None else None,
            first_transferred_time_s=after['time_s'] if after else None,load_transfer_passed=transfer))
    profile_passed=all(c['max_live_profile_difference_K']<5 and c['max_live_conversion_difference']<.02
               and abs(c['solid_mass_difference_fraction_initial'])<.01 for c in comparisons)
    schedule_identical=all(c['native_rows_scheduled']==c['independent_rows_scheduled'] for c in comparisons)
    passed=profile_passed and schedule_identical
    result=dict(runtime=name,case=cfg['case_id'],accepted_native_index=terminal['index'],accepted_native_time_s=terminal['time_s'],
        native_status=terminal['status'],comparison_passed=passed,profile_conversion_mass_passed=profile_passed,exact_row_schedule_identical=schedule_identical,
        qualification='Same-mesh numerical comparison, not independent physical calibration or a finer-mesh convergence claim. The reference is compared only through accepted native time.',
        model_sha256=hashlib.sha256((ROOT/'model/radial_model.py').read_bytes()).hexdigest(),
        config_sha256=hashlib.sha256((run/'config.json').read_bytes()).hexdigest(),comparisons=comparisons,removal_events=events,
        independent_energy_error=model.max_energy_error,independent_mass_error=model.max_mass_error)
    atomic(ROOT/'validation'/f'native_pulse_comparison_{cfg["case_id"]}.json',result)
    print(name,terminal['time_s'],passed,max(c['max_live_profile_difference_K'] for c in comparisons),events,flush=True)


def main():
    disks();queue=json.loads((ROOT/'configs/campaign_queue.json').read_text())
    for name in queue['ordered_runtimes']:
        if 'pulse7_' in name:compare(name)


if __name__=='__main__':main()

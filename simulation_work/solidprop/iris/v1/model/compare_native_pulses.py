"""Compare immutable accepted native pulse states with an independent assembly."""
import gzip
import argparse
import hashlib
import json
import math
import numpy as np
from radial_model import RadialModel
from ops import ROOT,TMP,atomic,disks,host_check


def compare(name,verification=False):
    run=TMP/'runs'/name
    if not (run/'state.json').exists():return
    terminal=json.loads((run/'state.json').read_text())
    limits=json.loads((ROOT/'configs/campaign_queue.json').read_text()).get('verified_historical_prefixes',{})
    if name in limits:
        terminal['index']=min(terminal['index'],limits[name])
        cutoff=json.loads((run/'checkpoints'/f'audit_{terminal["index"]:06d}.json').read_text())
        terminal['time_s']=cutoff['time_s'];terminal['status']='VERIFIED_HEATING_PREFIX_COOLING_WITHDRAWN'
    if terminal['index']<1:return
    cfg=json.loads((run/'config.json').read_text());g=cfg['geometry']
    audits={int(p.stem.split('_')[1]):json.loads(p.read_text()) for p in sorted((run/'checkpoints').glob('audit_*.json')) if int(p.stem.split('_')[1])<=terminal['index']}
    indices={terminal['index']}
    for t in [.1,1,2,5,7,10,20,30,60,90,127,150,200,250,300]:
        found=[i for i,a in audits.items() if abs(a['time_s']-t)<1e-8]
        indices.update(found)
    pulse=cfg['heating'].get('pulse_duration_s')
    cooling=[i for i,a in audits.items() if not a.get('exposure_on',True)]
    indices.update(cooling[:5])
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
    topology_checks=[a.get('native_live_elements_before_solve')==cfg['expected_elements']-a['rows_removed']*nf
                     for a in audits.values() if 'native_live_elements_before_solve' in a]
    cooling_checks=[not audits[i]['exposure_on'] and audits[i]['ablation_sink_W']==0
                    and audits[i]['hot_radiation_W']==0
                    and abs(audits[i]['gas_temperature_C']-cfg['heating']['ambient_temperature_C'])<1e-10
                    and abs(audits[i]['h_W_m2_K']-cfg['heating'].get('post_pulse_h_W_m2_K',8.))<1e-10
                    and audits[i]['hot_power_actual_W']<0 for i in cooling[:5]]
    result=dict(runtime=name,case=cfg['case_id'],accepted_native_index=terminal['index'],accepted_native_time_s=terminal['time_s'],
        native_reaction_temperature=cfg.get('native_reaction_temperature','inherited_endpoint_plus_half_increment'),
        native_material_dll_sha256=cfg.get('native_material_dll_sha256'),
        native_status=terminal['status'],comparison_passed=passed,profile_conversion_mass_passed=profile_passed,exact_row_schedule_identical=schedule_identical,
        persistent_native_topology_passed=all(topology_checks) if len(topology_checks)==len(audits) else None,
        cooling_transition_passed=all(cooling_checks) if len(cooling_checks)==5 else None,
        native_control_checks_passed=(all(topology_checks) and len(topology_checks)==len(audits) and all(cooling_checks)),
        qualification='Same-mesh numerical comparison, not independent physical calibration or a finer-mesh convergence claim. The reference is compared only through accepted native time.',
        model_sha256=hashlib.sha256((ROOT/'model/radial_model.py').read_bytes()).hexdigest(),
        config_sha256=hashlib.sha256((run/'config.json').read_bytes()).hexdigest(),comparisons=comparisons,removal_events=events,
        independent_energy_error=model.max_energy_error,independent_mass_error=model.max_mass_error)
    suffix=name if verification else cfg['case_id']
    atomic(ROOT/'validation'/f'native_pulse_comparison_{suffix}.json',result)
    print(name,terminal['time_s'],passed,max(c['max_live_profile_difference_K'] for c in comparisons),events,flush=True)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('runtimes',nargs='*')
    parser.add_argument('--verification',action='store_true',help='Keep runtime-specific evidence without replacing primary case comparisons')
    parser.add_argument('--require-pass',action='store_true')
    args=parser.parse_args()
    disks();queue=json.loads((ROOT/'configs/campaign_queue.json').read_text())
    for name in args.runtimes or queue['ordered_runtimes']:
        if args.runtimes or 'pulse7_' in name:
            result=compare(name,args.verification or name in queue.get('verification_runtimes',[]))
            if args.require_pass and (not result or not result['comparison_passed'] or not result['native_control_checks_passed']):
                raise RuntimeError('Native/independent comparison did not pass: '+name)


if __name__=='__main__':main()

"""Compare completed native resolutions without assigning results to queued runs."""
import hashlib
import json
from ops import ROOT,TMP,atomic,disks


def configuration_descriptor(cfg, manifest):
    """Keep changes in geometry/solver controls separate from physical inputs."""
    g=cfg['geometry'];n=cfg['numerics']
    physical={key:cfg.get(key) for key in [
        'case_id','case_material','initial_temperature_C','heating','material',
        'char_law','case_property_limit_C','stop_at_case_property_limit',
        'cf_radial_k','cf_inplane_k','cf_cp_constant_J_kg_K',
        'native_reaction_temperature','native_coupling_revision',
        'native_material_source_sha256','native_material_dll_sha256']}
    physical['cf_cp_scale']=cfg.get('cf_cp_scale',1.)
    physical['radial_dimensions']={key:g[key] for key in [
        'inner_radius_m','phenolic_outer_radius_m','outer_radius_m',
        'phenolic_thickness_m','aluminium_thickness_m']}
    physical['removal_controls']={key:n[key] for key in [
        'max_char_fraction_per_step','row_residual_mass_fraction']}
    physical['material_definition_sha256']=manifest['material_v0.apdl']
    physical['controller_sha256']=manifest['coupler.py']
    numerical={key:cfg.get(key) for key in [
        'macro_dt_s','minimum_dt_s','post_pulse_macro_dt_s',
        'post_pulse_initial_duration_s','post_pulse_initial_dt_s','end_time_s']}
    numerical.update({key:g[key] for key in [
        'phenolic_radial_rows','aluminium_radial_rows','angular_divisions',
        'axial_divisions','angle_deg','length_m']})
    numerical['mesh_measure_convention']=cfg.get('mesh_measure_convention','cylindrical_arc')
    numerical['native_heat_flow_tolerance']=n['native_heat_flow_tolerance']
    return dict(physical=physical,numerical=numerical,
                execution=dict(cores=cfg['ranks'],mode=cfg.get('parallel_mode','smp' if cfg['ranks']==1 else 'dis')))


def configuration_comparison(a,b):
    def differences(key):
        x,y=a[key],b[key]
        return {k:dict(coarse=x.get(k),fine=y.get(k)) for k in sorted(set(x)|set(y)) if x.get(k)!=y.get(k)}
    physical=differences('physical');numerical=differences('numerical')
    mesh={'phenolic_radial_rows','aluminium_radial_rows','angular_divisions','axial_divisions'}
    time={'macro_dt_s','minimum_dt_s','post_pulse_macro_dt_s','post_pulse_initial_duration_s','post_pulse_initial_dt_s'}
    changed=set(numerical)
    if physical:kind='different_physical_model'
    elif not changed:kind='same_discretization'
    elif changed<=time:kind='time_only'
    elif changed<=mesh:kind='mesh_only'
    elif changed<=mesh|time:kind='joint_mesh_time'
    else:kind='combined_numerical_changes'
    return dict(kind=kind,physical_model_identical=not physical,
                physical_changes=physical,numerical_changes=numerical,
                execution_changes=differences('execution'),
                isolated_spatial_comparison=kind=='mesh_only',
                qualification='Combined geometry, measures or solver-control changes cannot be attributed to radial mesh refinement alone.')


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
    # A terminal diagnostic may later supply a resolution level without editing
    # its sealed campaign_role. Never fall back to another runtime's evidence.
    candidates=[ROOT/'validation'/f'native_pulse_comparison_{name}.json',
                ROOT/'validation'/f'native_pulse_comparison_{cfg["case_id"]}.json']
    found=[(p,json.loads(p.read_text())) for p in candidates if p.exists()]
    found=[(p,c) for p,c in found if c['runtime']==name]
    if not found:return None
    comparison_path,comparison=found[0]
    assert comparison['comparison_passed'] and comparison['native_control_checks_passed']
    assert comparison['exact_row_schedule_identical'] and comparison['persistent_native_topology_passed']
    assert comparison['cooling_transition_passed']
    assert comparison['config_sha256']==a['config_sha256']
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
        independent_comparison_sha256=hashlib.sha256(comparison_path.read_bytes()).hexdigest(),
        configuration=configuration_descriptor(cfg,json.loads((runtime/'input_manifest.json').read_text())))


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
            configuration=configuration_comparison(a['configuration'],b['configuration'])
            full=a['complete'] and b['complete'] and abs(a['through_s']-b['through_s'])<1e-8
            censored=a['scope_limited'] and b['scope_limited']
            peak_diff={k:b['sampled_maxima'][k]['temperature_C']-a['sampled_maxima'][k]['temperature_C']
                       for k in a['sampled_maxima']} if full else None
            time_change=abs(b['scope_bracket_s'][1]/a['scope_bracket_s'][1]-1) if censored else None
            thickness=abs(b['remaining_mm']-a['remaining_mm'])
            target=max(.02,.01*a['initial_phenolic_mm'])
            passed=configuration['physical_model_identical'] and thickness<=target and ((full and max(map(abs,peak_diff.values()))<5) or (censored and time_change<.05))
            checks.append(dict(case=case,coarse=a['runtime'],fine=b['runtime'],passed=passed,
                complete_histories=full,both_scope_limited=censored,peak_differences_K=peak_diff,
                scope_time_relative_change=time_change,remaining_difference_mm=thickness,remaining_target_mm=target,
                configuration_comparison=configuration))
    atomic(ROOT/'validation/native_resolution_comparison.json',dict(complete=not pending,
        records=records,comparisons=checks,pending=pending,
        qualification='Completed native ANSYS comparisons only. Intermediate mesh failures remain visible even if the final refinement passes. Property-scope timing is not casing failure or burnthrough.'))
    print('Completed native records:',len(records),'comparisons:',len(checks),'pending:',len(pending))


if __name__=='__main__':
    main()

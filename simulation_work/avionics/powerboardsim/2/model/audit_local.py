"""Audit an isolated pull or coupon run. Retain partial histories separately from completed cases."""
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

from local_equilibrium import movement_table, recover, write_csv

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def table(path):
    values = np.atleast_1d(np.genfromtxt(path, delimiter=',', names=True))
    if not len(values) or not np.all(np.isfinite(values.view(float))):
        raise ValueError(f'Invalid native result table: {path.name}')
    return values


def fixture(folder, spec, config, source, listing, balance_path):
    history = table(folder/'history.csv')
    native = recover(folder/f"{spec['job']}.rst", source, movement_table(folder/'moving_supports.csv'), spec['cased'])
    converged = [(int(a),int(b)) for a,b in re.findall(r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED',listing)]
    if not converged or converged[0]!=(1,1) or any(right<=left or right[0]>left[0]+1 for left,right in zip(converged,converged[1:])):
        raise ValueError('Native solver listing contains a reset or a skipped load step')
    recorded=[(r['loadstep'],r['substep']) for r in native]
    if recorded!=converged:
        raise ValueError('Saved equilibrium states differ from the native completed step sequence')
    steps = np.array([r['loadstep'] for r in native])
    if not np.array_equal(np.unique(steps), np.arange(1,steps.max()+1)) or np.any(np.diff(steps)<0):
        raise ValueError('Load-step sequence resets or skips a stage')
    is_damage = spec['source'].startswith('damage_')
    start = config.get('pull_start_time',0)
    pull = [row for row in native if row['time'] > start+1e-9]
    if not pull:
        raise ValueError('Fixture did not reach the pull stage')
    matching = history[history['time']>start+1e-9]
    if len(matching)!=len(pull) or not np.allclose(matching['time'],[x['time'] for x in pull],atol=1e-7,rtol=0):
        raise ValueError('Native history does not match the converged RST time series')
    forces = np.array([x['cell_fx_N'] for x in pull])
    if not np.allclose(forces, matching['fx_N'], rtol=1e-6,atol=1e-5):
        raise ValueError('Native POST1 cell force differs from the RST reactions')
    if 'bottom_pilots' in config:
        clamps = table(folder/('set_inventory.csv' if is_damage else 'contact_history.csv'))
        fields = ('clamp1_N','clamp2_N') if is_damage else ('washer1_RFz','washer2_RFz')
        lock = clamps[np.isclose(clamps['time'],start,rtol=0,atol=1e-7)]
        if len(lock)!=1 or any(abs(abs(float(lock[k][0]))-config['preload_N'])>.2 for k in fields):
            raise ValueError('One or more washers failed to retain the preload at locking')
        if not is_damage:
            if any(np.ptp(clamps[k][clamps['time']>=start])>1e-7 for k in ('washer1_uz','washer2_uz')):
                raise ValueError('Locked washer heights changed during pull')
    force = np.array([[r['force_N_'+ax] for ax in 'xyz'] for r in native])
    torque = np.array([[r['moment_cell_Nmm_'+ax] for ax in 'xyz'] for r in native])
    cell_force = np.abs([r['cell_fx_N'] for r in native])
    max_fx_rel = float(np.max(abs(force[:,0])/np.maximum(1,cell_force)))
    max_force = np.max(abs(force),axis=0)
    max_torque = np.max(abs(torque),axis=0)
    # Use the same practical force limits as the prior fixture and a lateral moment
    # check based on the distance (42.5 mm) from the cell centre to a washer centre.
    moment_norm = np.linalg.norm(torque[steps>=3] if start else torque,axis=1)
    pull_scale = np.maximum(1.,np.abs(forces)*42.5)
    if len(moment_norm)!=len(pull_scale):
        raise ValueError('Moment audit and pull states differ')
    rel_moment = float(np.max(moment_norm/pull_scale))
    balance_path.parent.mkdir(parents=True,exist_ok=True)
    write_csv(native,balance_path)
    if max_fx_rel>=.01 or max_force[1]>=.1 or max_force[2]>=.2 or rel_moment>=.01:
        raise ValueError(f'Equilibrium outside tolerance: {max_fx_rel:g}, {max_force}, {rel_moment:g}')
    end = config.get('end_time',1)
    reached = (abs(pull[-1]['time']-end)<1e-6 and
               abs(pull[-1]['ux_mm']-config['sign']*config['displacement_mm'])<1e-5)
    data = dict(states=len(native), last_time=pull[-1]['time'], last_ux_mm=pull[-1]['ux_mm'],
                last_fx_N=pull[-1]['cell_fx_N'], peak_abs_fx_N=float(np.max(abs(forces))),
                max_abs_force_residual_N=max_force.tolist(), max_abs_moment_at_cell_Nmm=max_torque.tolist(),
                max_relative_lateral_imbalance=max_fx_rel, max_relative_pull_moment_residual=rel_moment)
    if is_damage and 'dtop' in matching.dtype.names:
        from nickel_damage import summarize
        data.update(summarize(clamps,native))
        damage=np.maximum.reduce([matching[k] for k in ('dtop','dmid','dbot')])
        data['max_reported_damage']=float(np.max(damage))
        data['max_reported_equivalent_plastic_strain']=float(np.max(matching['peeq']))
        if data['max_reported_equivalent_plastic_strain']>1.55:
            raise ValueError('Nickel plastic strain exceeded the material-law scope')
        assert np.allclose(damage,clamps['damage'][clamps['time']>start+1e-9],rtol=1e-6,atol=1e-8)
    elif 'max_eppl' in matching.dtype.names:
        data['max_reported_equivalent_plastic_strain']=float(np.max(matching['max_eppl']))
    if 'absolute_search_mm' in spec:
        pairs=table(folder/'case_pairs.csv')
        for pid in (861,862):
            a=pairs[pairs['pair']==pid]
            if not np.array_equal(a['set'],[r['native_set'] for r in native]) or not np.allclose(a['time'],[r['time'] for r in native]):
                raise ValueError(f'Missing contact history on case pair {pid}')
            if not np.all(a['elements']==a['elements'][0]) or a['elements'][0]<=0 or np.any((a['closed']<0)|(a['closed']>a['elements'])):
                raise ValueError(f'Invalid surface inventory on case pair {pid}')
            if np.any(a['closed'][a['time']<=start]>0):
                raise ValueError(f'Raised fixture closed an initial gap during the held-cell preload: {pid}')
            engaged=np.flatnonzero(a['closed']>0)
            data[f'pair_{pid}']=dict(closed_at_end=int(a['closed'][-1]),peak_centroid_pressure_MPa=float(max(a['p_MPa'])),
                peak_unfiltered_corner_value_mm=float(max(a['pen_mm'])),
                contact_travel_bracket_mm=None if not len(engaged) else [native[max(0,engaged[0]-1)]['ux_mm'],native[engaged[0]]['ux_mm']])
        data['screw_support_fx_N']=native[-1]['screw_support_N_x']
        data['neighbour_support_fx_N']=native[-1]['neighbor_support_N_x']
    return data,reached


def audit(case, campaign):
    receipts = ROOT/'.runtime/receipts'/campaign/case
    folder = ROOT/'.runtime/archive'/campaign/case
    status = read(receipts/'status.json')
    ledger = read(receipts/'archived.json')
    spec = read(folder/'local_job.json')
    catalog='local_contact_retries.json' if case.endswith('_pin1') else 'local_jobs.json'
    if spec.get('case_template') and spec['source'].startswith('lateral_grip_'):
        catalog='perfect_grip_cases.json'
    if spec.get('sensitivity_reference'):catalog='damage_variant_inputs.json'
    if spec.get('common_load_parent'):catalog='common_pull_resolution.json'
    if spec.get('detection_parent'):catalog='pull_detection_control.json'
    if case.startswith('snug125_'):
        catalog='snug125/local_sensitivity_inputs.json' if spec.get('snug_sensitivity') else 'snug125/local_inputs.json'
    if case.startswith('snug125_') and case.endswith('_m15'):
        catalog=catalog.replace('.json','_m15.json')
    if case.startswith('snug125_') and case.endswith('_pin1_m3'):
        catalog='snug125/local_inputs_m3.json'
    if spec.get('snug_bearing_control'):
        catalog='snug125/local_bearing_inputs.json'
    manifest = read(ROOT/'validation'/catalog)[case]
    assert hashlib.sha256((folder/'local_job.json').read_bytes()).hexdigest()==manifest['spec_sha256']
    assert spec['case']==ledger['case']==status['case']==case and status['phase']=='solver_complete'
    assert all((folder/f['name']).stat().st_size==f['bytes'] for f in ledger['files'])
    cfgdir = ROOT/'.runtime/local_inputs'/spec['source']
    cfg = read(cfgdir/'config.json')
    if spec.get('common_load_parent') or spec.get('detection_parent') or spec.get('snug_bearing_control'):
        cfg.update(end_time=spec['end_time'],displacement_mm=spec['displacement_mm'])
    listing = (folder/'solve.out').read_text(errors='replace')
    if 'RUN COMPLETED' not in listing or (folder/'REJECTED_LOAD_HISTORY.txt').exists():
        raise ValueError('Native run lacks a valid completion record')
    if spec['coupon']:
        from coupon_audit import fresh as check_coupon
        data,reached=check_coupon(folder,spec,cfg,{f['name']:f['sha256'] for f in ledger['files']})
    else:
        balance_path=ROOT/'.runtime/post'/campaign/case/'whole_fixture_balance.csv'
        data,reached=fixture(folder,spec,cfg,cfgdir,listing,balance_path)
        if spec['job']=='tear':
            from nickel_pull_balance import native_check
            native_check(folder,balance_path,campaign,cfg['pull_start_time'])
    if not spec['coupon'] and spec['source'].startswith('damage_') and 'damage_onset_bracket' in data:
        from damage_footprint import run as damage_maps
        from film_identity import digest
        data['damage_footprint_sha256']=digest(damage_maps(case,campaign))
    if spec.get('snug_bearing_control'):
        from rocking_bearing import audit_joint
        from film_identity import digest
        data['joint_check_sha256']=digest(audit_joint(case,campaign))
    complete = bool(status['native_clean']) and reached
    data.update(case=case,source=spec['source'],campaign=campaign,full_requested_path=complete,
                scope='Completed numerical fixture' if complete else 'Partial converged path; endpoint under review',
                rst_sha256=next(f['sha256'] for f in ledger['files'] if f['name']==spec['job']+'.rst'))
    if case.startswith('snug125_') and case.endswith('_m15'):
        from snug_local_core_trial import verify_production_runtime
        data['solver_runtime']=verify_production_runtime(case,campaign,spec,status,listing)
    dest=ROOT/'validation'/('local' if complete else 'partial_local')
    dest.mkdir(exist_ok=True)
    from film_identity import write_json
    if case.startswith(('stand3_','snug125_')) and not spec['coupon']:
        from installation_material import run as check_material
        draft=ROOT/'.runtime/post'/campaign/case/'fixture_verdict.json'
        write_json(draft,data)
        check_material(case,campaign,pull=True,verdict_path=draft)
        if case.startswith('snug125_') or spec['source'].startswith('damage_cont'):
            from pull_contact_audit import verify as check_hardware
            check_hardware(case,draft)
    if spec.get('common_load_parent') and complete:
        from common_pull_resolution import check as check_resolution
        check_resolution(case,campaign)
    write_json(dest/(case+'.json'),data)
    if spec.get('snug_bearing_control'):
        from snug_rocking_pull import compare as compare_mounts
        compare_mounts(case,dest/(case+'.json'))
    elif (case.startswith('snug125_') and case.endswith(('_m15','_m3'))
            and spec['source'] in ('lateral_friction_locked','lateral_friction_locked_minus')):
        from snug_directional_result import run as compare_bare
        compare_bare(case)
    if case.startswith('snug125_') and case.endswith('_m15') and spec['source'].startswith('damage_cont'):
        from snug_damage_family import compare_case
        pair=compare_case(case)
        if spec['source']=='damage_cont_nominal' and pair and 'at_common_travel' in pair:
            from compare_pull_laws import compare
            branch=case.split('_damage_')[0]
            forward=branch+'_lateral_friction_locked_pin1_m15'
            from snug_damage_family import result_file
            if result_file(forward) and result_file('bare_lateral_friction_locked'):
                compare(branch)
    if case=='bare_damage_cont_nominal':
        from damage_repeat import compare as compare_damage
        compare_damage(case,campaign)
    if case.startswith('bare_lateral_'):
        from pull_reference import compare
        compare(case,campaign)
    print(data['scope'],case,flush=True)

if __name__ == '__main__':
    audit(*sys.argv[1:])

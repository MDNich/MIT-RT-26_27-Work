"""Reconstruct reaction from accepted native temperatures, without a new solve."""
import gzip
import hashlib
import json
import math
import numpy as np
from ops import ROOT, TMP, atomic, disks, host_check
from validate_run import validate
from radial_model import RadialModel


def reconstruct(name):
    run = TMP/'runs'/name
    checked = validate(run)
    cfg = json.loads((run/'config.json').read_text())
    g = cfg['geometry']; n = g['phenolic_radial_rows']
    plane = (g['angular_divisions']+1)*(g['axial_divisions']+1)
    nf = g['faces_per_row']
    N = np.array([[(1+1/math.sqrt(3))/2, (1-1/math.sqrt(3))/2],
                  [(1-1/math.sqrt(3))/2, (1+1/math.sqrt(3))/2]])
    old = np.full(n+1, cfg['initial_temperature_C'], dtype=float)
    modes = ['midpoint', 'endpoint', 'end_plus_half_increment']
    alpha = {mode:np.zeros((n,2)) for mode in modes}
    errors = {mode:0. for mode in modes}
    samples = []; history_hash = hashlib.sha256()
    for index in range(1, checked['accepted_steps']+1):
        if index % 100 == 0:host_check()
        path = run/'checkpoints'/f'state_{index:06d}.json.gz'
        history_hash.update(path.read_bytes())
        with gzip.open(path, 'rt') as f:s = json.load(f)
        a = json.loads((run/'checkpoints'/f'audit_{index:06d}.json').read_text())
        assert a['native_substep'] == 1
        T = np.array([np.mean([s['temperatures'][str(1+j*plane+k)] for k in range(plane)]) for j in range(n+1)])
        oldg = old[:-1,None]*N[None,:,0]+old[1:,None]*N[None,:,1]
        newg = T[:-1,None]*N[None,:,0]+T[1:,None]*N[None,:,1]
        native = np.array([np.mean([s['alpha'][str(1+j*nf+k)] for k in range(nf)]) for j in range(n)])
        first = a['rows_removed']; current = {}
        for mode in modes:
            temp = {'midpoint':.5*(oldg+newg), 'endpoint':newg,
                    'end_plus_half_increment':1.5*newg-.5*oldg}[mode]
            rate = 333*np.exp(-64081/(8.31446261815324*np.maximum(temp+273.15,1.)))
            alpha[mode][first:] = 1-(1-alpha[mode][first:])*np.exp(-rate[first:]*a['dt_s'])
            current[mode] = float(np.max(np.abs(alpha[mode][first:].mean(axis=1)-native[first:])))
            errors[mode] = max(errors[mode], current[mode])
        if index in [1,8,80,160,400,560,checked['accepted_steps']]:
            samples.append(dict(index=index,time_s=a['time_s'],conversion_errors=current))
        old = T
    # This is a diagnostic assertion about the existing DLL, not approval of
    # that time convention as the intended midpoint reaction model.
    assert errors['end_plus_half_increment'] < 2e-6
    assert errors['midpoint'] > 1e-4
    result = dict(runtime=name, native=checked, max_conversion_errors=errors,
                  samples=samples, accepted_state_archive_sha256=history_hash.hexdigest(),
                  native_material_source_sha256=hashlib.sha256((run/'usermatth.F').read_bytes()).hexdigest(),
                  native_material_dll_sha256=hashlib.sha256((run/'usermatthLib.dll').read_bytes()).hexdigest(),
                  qualification='Accepted native-temperature replay diagnoses the inherited temperature-increment convention. It does not validate kinetics or physical motor lifetime.',
                  conclusion='The existing DLL agrees with endpoint temperature plus half the increment, not the documented midpoint.',
                  source='https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_prog/Z7K4r1e5lcd.html')
    atomic(ROOT/'validation/native_temperature_convention.json', result)
    print(json.dumps(errors, indent=2))


def compare_shifted_law(name):
    """Compare the unchanged native run with its actual inherited time law."""
    run=TMP/'runs'/name
    cfg=json.loads((run/'config.json').read_text())
    reference=json.loads((ROOT/'validation'/f'native_pulse_comparison_{name}.json').read_text())
    targets=[row['time_s'] for row in reference['comparisons']]
    model=RadialModel(cfg,reaction_temperature='endpoint_plus_half_increment')
    _,history,snaps=model.run(targets[-1],dt=cfg['macro_dt_s'],post_dt=cfg['post_pulse_macro_dt_s'],targets=targets,check=host_check)
    rows=[]
    for row in reference['comparisons']:
        s=snaps[row['time_s']];common=max(row['native_rows_scheduled'],s.layer)
        error=float(np.max(np.abs(s.T[common:]-np.array(row['native_temperature_C'])[common:])))
        rows.append(dict(time_s=s.time, max_profile_difference_K=error,
                         native_layer=row['native_rows_scheduled'],independent_layer=s.layer))
    result=dict(qualification='Diagnostic independent reproduction of the inherited native time convention. This does not replace the intended midpoint model or validate physical kinetics.',
                runtime=name,reaction_temperature='endpoint_plus_half_increment',comparisons=rows,
                maximum_profile_difference_K=max(r['max_profile_difference_K'] for r in rows),
                model_sha256=hashlib.sha256((ROOT/'model/radial_model.py').read_bytes()).hexdigest(),
                original_comparison_sha256=hashlib.sha256((ROOT/'validation'/f'native_pulse_comparison_{name}.json').read_bytes()).hexdigest())
    atomic(ROOT/'validation'/f'temperature_convention_resolution_{name}.json',result)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    disks();name='sustainer_al_pulse7_n80_substepguard_default_control20'
    reconstruct(name);compare_shifted_law(name)

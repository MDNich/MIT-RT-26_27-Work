"""Compare completed native tolerance controls, without changing sealed inputs."""
import copy
import gzip
import hashlib
import json
from pathlib import Path

from compare_native_pulses import compare
from ops import ROOT, TMP, atomic, disks, host_check
from validate_run import validate


NAMES = [f'sustainer_al_pulse7_n80_substepguard_{kind}_control20'
         for kind in ('default', 'tight')]


def load_state(run, index):
    with gzip.open(run/'checkpoints'/f'state_{index:06d}.json.gz', 'rt') as f:
        return json.load(f)


def main():
    disks()
    runs = [TMP/'runs'/name for name in NAMES]
    for run in runs:
        done = run/'phase_run_exit.json'
        if not done.exists():
            raise SystemExit(f'{run.name}: not finished; no comparison published')
        assert json.loads(done.read_text(encoding='utf-8-sig'))['ok']
    validations = [validate(run) for run in runs]
    configs = [json.loads((run/'config.json').read_text()) for run in runs]
    normalized = copy.deepcopy(configs)
    for cfg in normalized:
        cfg.pop('windows_root')
        cfg.pop('host_runtime')
        cfg['numerics'].pop('native_heat_flow_tolerance', None)
    assert normalized[0] == normalized[1], 'Controls differ beyond tolerance/paths'
    assert 'native_heat_flow_tolerance' not in configs[0]['numerics']
    assert configs[1]['numerics']['native_heat_flow_tolerance'] == 1e-5
    assert all(v['status'] == 'COMPLETED_HORIZON' for v in validations)
    assert validations[0]['accepted_steps'] == validations[1]['accepted_steps']
    g = configs[0]['geometry']
    plane = (g['angular_divisions']+1)*(g['axial_divisions']+1)
    nf = g['faces_per_row']
    history = []
    for index in range(1, validations[0]['accepted_steps']+1):
        if index % 100 == 0:
            host_check()
        a, b = [load_state(run, index) for run in runs]
        assert abs(a['time_s']-b['time_s']) < 1e-9
        common = max(a['layer'], b['layer'])
        delta = [abs(a['temperatures'][nid]-b['temperatures'][nid])
                 for nid in a['temperatures'] if int(nid) >= 1+common*plane]
        conversion = [abs(a['alpha'][eid]-b['alpha'][eid])
                      for eid in a['alpha'] if int(eid) >= 1+common*nf]
        row = dict(index=index, time_s=a['time_s'],
                   max_live_profile_difference_K=max(delta),
                   max_live_conversion_difference=max(conversion),
                   default_layer=a['layer'], tight_layer=b['layer'])
        for label, node in [('inner', 1+g['phenolic_radial_rows']*plane),
                            ('outer', 1+(g['phenolic_radial_rows']+g['aluminium_radial_rows'])*plane)]:
            row[f'case_{label}_difference_K'] = b['temperatures'][str(node)]-a['temperatures'][str(node)]
        history.append(row)
    independent = []
    for name in NAMES:
        compare(name, verification=True)
        p = ROOT/'validation'/f'native_pulse_comparison_{name}.json'
        data = json.loads(p.read_text())
        independent.append(dict(runtime=name, comparison_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                                profile_conversion_mass_passed=data['profile_conversion_mass_passed'],
                                exact_row_schedule_identical=data['exact_row_schedule_identical'],
                                max_profile_difference_K=max(c['max_live_profile_difference_K'] for c in data['comparisons']),
                                cooling_transition_passed=data['cooling_transition_passed'],
                                persistent_native_topology_passed=data['persistent_native_topology_passed']))
    result = dict(qualification='Native numerical tolerance comparison only; no physical calibration or mesh-convergence claim.',
                  native=validations, independent_comparisons=independent,
                  max_native_pair_profile_difference_K=max(h['max_live_profile_difference_K'] for h in history),
                  max_native_pair_conversion_difference=max(h['max_live_conversion_difference'] for h in history),
                  exact_native_pair_row_schedule=all(h['default_layer']==h['tight_layer'] for h in history),
                  history=history,
                  analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    atomic(ROOT/'validation/native_solver_tolerance_comparison.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['native','history']}, indent=2))


if __name__ == '__main__':
    main()

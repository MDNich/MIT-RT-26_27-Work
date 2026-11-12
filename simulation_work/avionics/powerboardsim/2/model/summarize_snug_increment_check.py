"""Summarize a closed selected increment control without rerunning its audits."""
import argparse

from audit_local import ROOT, read
from film_identity import digest, verified, write_json


def run(screw='nylon'):
    assert screw in ('nylon', 'aluminium')
    case = f'snug125_{screw}_lateral_friction_locked_steps_m15'
    root = ROOT / 'validation/snug125'
    receipt = ROOT / '.runtime/receipts/nov08_01' / case
    archive = ROOT / '.runtime/archive/nov08_01' / case
    paths = dict(comparison=root / f'{screw}_local_step_comparison.json',
                 fixture=ROOT / 'validation/local' / (case + '.json'),
                 material=ROOT / 'validation/pull_material' / (case + '.json'),
                 contact=ROOT / 'validation/pulls' / (case + '_contact.json'),
                 input_registry=root / ('aluminium_local_pull_step_input.json' if screw == 'aluminium'
                                        else 'local_pull_step_input.json'))
    comparison, fixture, material, contact, registry = [read(p) for p in paths.values()]
    spec = registry[case]
    status = read(receipt / 'status.json')
    ledger = read(receipt / 'archived.json')
    hashes = {r['name']: r['sha256'] for r in ledger['files']}
    assert status['case'] == ledger['case'] == fixture['case'] == case
    assert status['phase'] == 'solver_complete' and status['native_clean'] and status['exit'] == 0
    assert (receipt / 'released.txt').is_file() and fixture['full_requested_path']
    states = fixture['states']
    assert fixture['solver_runtime']['cores'] == spec.get('runtime_cores', 4)
    assert status['input_sha256'].lower() == spec['input_sha256']
    assert fixture['rst_sha256'] == material['rst_sha256'] == comparison['cased']['rst_sha256'] == hashes['pull.rst']
    assert contact['rst_sha256'] == fixture['rst_sha256'] and contact['converged_states'] == states
    assert comparison['staged_input_sha256'] == material['input_sha256'] == spec['input_sha256'] == hashes['model.inp']
    assert material['contact_verdict_sha256'] == digest(paths['fixture'])
    if screw == 'nylon':
        assert states == 42 and not material['first_reference_crossings']
    for name in ('model.inp', 'pull.rst', 'solve.out'):
        verified(archive / name, hashes[name])
    checkpoint = '47' if screw == 'nylon' else '15'
    parent_path = root / f'snug125_{screw}_lateral_friction_locked_pin1_m15_ls3_ss{checkpoint}_energy.json'
    verified(parent_path, comparison['reference_sha256'])
    parent = read(parent_path)
    rows = comparison['matched_stations']
    assert len(rows) == len(spec['steps']) == 13
    if screw == 'nylon':
        assert all(r['both_within_parent_screens'] for r in rows)
    assert rows[-1]['travel_mm'] == fixture['last_ux_mm'] == .219375
    end = rows[-1]
    peak_force_change = max(abs(r['force_N'][1] / r['force_N'][0] - 1) for r in rows)
    history = comparison['cased']['history']
    equal = comparison['at_bare_endpoint_force']
    bracket = [next(r for r in history if r['native_set'] == n) for n in equal['native_sets']]
    data = dict(case=case, input_sha256=hashes['model.inp'], rst_sha256=hashes['pull.rst'],
                source_sha256={k: digest(p) for k, p in paths.items()},
                archive_manifest_sha256=digest(receipt / 'archived.json'),
                status_sha256=digest(receipt / 'status.json'),
                converged_states=states, full_requested_path=True, matched_stations=len(rows),
                maximum_matched_force_change_percent=100 * peak_force_change,
                final_travel_mm=end['travel_mm'], final_force_N=end['force_N'],
                final_work_mJ=end['work_mJ'],
                final_work_change_percent=100 * (end['work_mJ'][1] / end['work_mJ'][0] - 1),
                equal_force_N=equal['force_N'],
                equal_force_travel_mm=[parent['at_bare_endpoint_force']['travel_mm'], equal['travel_mm']],
                refined_equal_force_travel_bracket_mm=[r['travel_mm'] for r in bracket],
                equal_force_work_mJ=[parent['at_bare_endpoint_force']['external_work_mJ'], equal['external_work_mJ']],
                max_force_residual_N=max(fixture['max_abs_force_residual_N']),
                max_work_balance_residual_mJ=comparison['cased']['max_supported_balance_residual_mJ'],
                first_parent_mesh_PLA_reference_crossings=material['first_reference_crossings'],
                scope='Same bilinear nickel, mesh, local fixed-support fixture and displacement ramp. '
                      'Only contact-transition increments change. All 42 saved equilibria pass the existing fixture screens. '
                      'Force changes are below 1 percent at the 13 matched stations; final integrated work changes by about 3 percent. '
                      'Early contact work is more step-sensitive. This single increment control does not establish full convergence, '
                      'a physical failure load or a converged PLA limit. No refined corner bound is transferred to the changed deck.')
    if screw == 'aluminium':
        data['scope'] = (
            'Same bilinear nickel, mesh, local fixed-support fixture and displacement ramp. '
            'Only contact-transition increments change; the approved twelve-core SMP runtime is retained. '
            'Force and work comparisons assess increment sensitivity only. The original parent has a '
            'nonconverged refined PLA corner reference crossing at 0.107--0.132 mm; its later values '
            'are numerical continuation. That exact-deck bound is not transferred to this control. '
            'Neither parent-mesh screening nor agreement of reactions establishes full convergence '
            'or a physical failure load.')
        data['matched_stations_within_both_parent_mesh_screens'] = sum(
            r['both_within_parent_screens'] for r in rows)
    write_json(root / f'{screw}_increment_completion.json', data)
    print({k: data[k] for k in ('converged_states', 'maximum_matched_force_change_percent', 'final_force_N', 'final_work_mJ')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aluminium', action='store_true')
    run('aluminium' if parser.parse_args().aluminium else 'nylon')

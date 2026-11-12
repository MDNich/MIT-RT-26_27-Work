"""Summarize existing final audits and plot the selected target-resolution control."""
from collections import Counter

import numpy as np

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from report_plot import plt

AUDIT = ROOT / 'validation/snug125'
CASE = 'snug125_nylon_lateral_friction_locked_target4_m15'


def target_control():
    receipt = ROOT / '.runtime/receipts/nov08_01' / CASE
    archive = ROOT / '.runtime/archive/nov08_01' / CASE
    paths = dict(comparison=AUDIT / (CASE + '_contact_resolution.json'),
                 candidate=AUDIT / (CASE + '_moving_contact.json'),
                 reference=AUDIT / 'snug125_nylon_lateral_friction_locked_steps_m15_moving_contact.json',
                 fixture=ROOT / 'validation/local' / (CASE + '.json'),
                 material=ROOT / 'validation/pull_material' / (CASE + '.json'),
                 input_registry=AUDIT / 'local_target_control.json')
    comparison, candidate, reference, fixture, material, registry = [read(p) for p in paths.values()]
    status, ledger = read(receipt / 'status.json'), read(receipt / 'archived.json')
    hashes = {r['name']: r['sha256'] for r in ledger['files']}
    assert status['phase'] == 'solver_complete' and status['exit'] == 0 and status['native_clean']
    assert (receipt / 'released.txt').is_file() and fixture['full_requested_path']
    assert fixture['states'] == 20 and fixture['last_ux_mm'] == .04
    assert fixture['rst_sha256'] == candidate['rst_sha256'] == material['rst_sha256'] == hashes['pull.rst']
    assert registry[CASE]['input_sha256'] == status['input_sha256'].lower() == hashes['model.inp']
    assert candidate['verdict_sha256'] == material['contact_verdict_sha256'] == digest(paths['fixture'])
    assert not material['first_reference_crossings']
    assert comparison['reference_history_sha256'] == digest(paths['reference'])
    assert comparison['candidate_history_sha256'] == digest(paths['candidate'])
    assert comparison['sources'] == [reference['rst_sha256'], candidate['rst_sha256']]
    for name in ('model.inp', 'pull.rst', 'solve.out'):
        verified(archive / name, hashes[name])
    rows = comparison['common_native_travel']
    assert len(rows) == 11 and rows[-1]['travel_mm'] == [.04, .04]
    max_force = max(abs(r['cell_force_N'][1] / r['cell_force_N'][0] - 1) for r in rows)
    loaded = [r for r in rows if r['loaded_area_mm2'][0] > 0]
    first = next(i for i, r in enumerate(rows) if r['loaded_area_mm2'][1] > 0)
    equal_travel = []
    for bracket in comparison['surrounding_force_states']:
        a, b = bracket
        equal_travel.append(float(np.interp(comparison['signed_bare_endpoint_N'],
                                            [a['cell_force_N'], b['cell_force_N']],
                                            [a['ux_mm'], b['ux_mm']])))
    summary = dict(case=CASE, converged_states=20, full_requested_path=True,
                   input_sha256=hashes['model.inp'], rst_sha256=hashes['pull.rst'],
                   source_sha256={k: digest(v) for k, v in paths.items()},
                   archive_manifest_sha256=digest(receipt / 'archived.json'),
                   status_sha256=digest(receipt / 'status.json'), matched_stations=11,
                   maximum_matched_force_change_percent=100 * max_force,
                   first_contact_bracket_mm=[rows[first-1]['travel_mm'][1], rows[first]['travel_mm'][1]],
                   final_comparison=rows[-1],
                   maximum_loaded_area_change_percent=max(100*abs(r['loaded_area_mm2'][1]/r['loaded_area_mm2'][0]-1) for r in loaded),
                   equal_force_N=comparison['signed_bare_endpoint_N'], equal_force_travel_mm=equal_travel,
                   force_brackets=comparison['surrounding_force_states'],
                   max_force_residual_N=max(fixture['max_abs_force_residual_N']),
                   first_parent_mesh_PLA_reference_crossings=material['first_reference_crossings'],
                   scope='Same 1.5 mm PLA mesh, bilinear nickel, fixed neighbours and four-core SMP. Only the moving rigid cell target changes from 8856 to 35162 triangles. Compare pressures at actual common travel; retain native force brackets. One target refinement does not establish full local contact convergence or physical sleeve strength.')
    fig, axes = plt.subplots(1, 3, figsize=(8.2, 2.6), layout='constrained')
    for ax, key, label in zip(axes, ('cell_force_N', 'loaded_area_mm2', 'peak_pressure_MPa'),
                             (r'Applied force [N]', r'Loaded area [mm$^2$]', r'Peak pressure [MPa]')):
        for i, color, marker, label_text in [(0, '#08357E', 'o', r'8,856 target triangles'),
                                           (1, '#38761D', 's', r'35,162 target triangles')]:
            ax.plot([r['travel_mm'][i] for r in rows], [r[key][i] for r in rows],
                    color=color, marker=marker, ms=3, lw=1.2, label=label_text)
        ax.set(xlabel=r'Cell travel [mm]', ylabel=label, xlim=(0, .041))
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='y', alpha=.15)
    axes[0].legend(frameon=False, fontsize=8)
    figure = ROOT / 'docs/figures/snug-target-resolution.pdf'
    fig.savefig(figure)
    plt.close(fig)
    summary['figure_sha256'] = digest(figure)
    write_json(AUDIT / 'target_resolution_completion.json', summary)
    print('Target control:', summary['maximum_matched_force_change_percent'], 'percent maximum force change')


def scope_outcomes():
    path = AUDIT / 'main_validation_scope.json'
    scope = read(path)
    failures_path = AUDIT / 'main_shell_preprocessing_failures.json'
    failures = {r['case']: r for r in read(failures_path)['cases']}
    blocked = {c: r['case'] for r in failures.values() for c in r['blocked_undispatched_dependents']}
    rows = []
    for item in scope['cases']:
        case = item['case']
        receipt = ROOT / '.runtime/receipts/nov08_01' / case
        if case in blocked:
            assert not (receipt / 'dispatch.json').exists()
            rows.append(dict(case=case, disposition='blocked', failed_ancestor=blocked[case]))
            continue
        status = read(receipt / 'status.json')
        if case in failures:
            verified(receipt / 'status.json', failures[case]['status_sha256'])
            assert status['phase'] == 'failed'
            rows.append(dict(case=case, disposition='preprocessing_failed', failure=failures[case]))
            continue
        assert status['phase'] == 'solver_complete' and (receipt / 'released.txt').is_file()
        verdicts = [p for kind in ('global', 'local', 'partial_local')
                    if (p := ROOT / 'validation' / kind / (case + '.json')).is_file()]
        assert len(verdicts) == 1
        rows.append(dict(case=case, disposition='audited',
                         verdict=str(verdicts[0].relative_to(ROOT)), verdict_sha256=digest(verdicts[0]),
                         status_sha256=digest(receipt / 'status.json'),
                         archive_manifest_sha256=digest(receipt / 'archived.json'),
                         native_clean=status.get('native_clean'), full_requested_path=read(verdicts[0]).get('full_requested_path')))
    counts = dict(Counter(r['disposition'] for r in rows))
    assert counts == dict(audited=16, preprocessing_failed=2, blocked=6)
    geometry = ROOT / 'geometry/candidates/Balius-native-verification.STEP'
    verified(geometry, '43016e8435a85fc9ad33346ae11c0051102591c85a1fcee5ddd5658f75ca98ef')
    write_json(AUDIT / 'main_validation_outcomes.json',
               dict(scope_sha256=digest(path), geometry_sha256=digest(geometry),
                    tab_to_PCB_spacing_mm=1.25, counts=counts, cases=rows,
                    failure_record_sha256=digest(failures_path), deferred_count=len(scope['deferred_cases']),
                    pending_selected_cases=[],
                    scope='Finite computational campaign closed with audited results, documented partial paths and explicit unresolved controls. Audited does not mean physical validation or material qualification. No replacement sweep is authorized. Publication and account-skill shutdown receipts are separate.'))
    print('Finite outcomes:', counts)


if __name__ == '__main__':
    target_control()
    scope_outcomes()

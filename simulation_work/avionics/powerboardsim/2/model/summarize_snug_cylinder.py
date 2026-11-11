"""Summarize the selected cylindrical preload check without widening the campaign."""
import math
from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from stage_snug_fit import AUDIT, input_record

TIGHT = 'snug125_aluminium_cylinder_tol0001_static'
OLD = 'snug125_aluminium_cylinder_static'
NOMINAL = 'snug125_aluminium_tol001_static'

def run():
    rows = {}
    for case in (NOMINAL, OLD, TIGHT):
        spec = input_record(case)
        names = {key: AUDIT / f'{case}_{key}.json' for key in ('seats', 'contacts', 'installed')}
        seats, contacts, installed = (read(names[k]) for k in ('seats', 'contacts', 'installed'))
        assert seats['input_sha256'] == spec['input_sha256']
        assert seats['rst_sha256'] == contacts['rst_sha256'] == installed['rst_sha256']
        verified(names['contacts'], seats['native_contact_audit_sha256'])
        assert len(seats['states']) == len(contacts['resultant_force_check']) == 8
        for s, c in zip(seats['states'], contacts['resultant_force_check'], strict=True):
            assert s['native_set'] == c['native_set']
            assert math.isclose(math.dist(s['native_force_on_cells_XYZ_N'], [0, 0, 0]), c['resultant_N'], abs_tol=1e-12)
        locked = seats['states'][-1]
        rows[case] = dict(input_sha256=spec['input_sha256'], rst_sha256=seats['rst_sha256'],
            source_sha256={k: digest(p) for k, p in names.items()},
            all_eight_force_screens_passed=all(s['within_force_screens'] for s in seats['states']),
            locked_force_N=contacts['resultant_force_check'][-1]['resultant_N'],
            locked_balance_residual_N=locked['four_tab_force_balance_residual_N'],
            locked_relative_residual=locked['relative_vector_residual'],
            loaded_faces_at_lock=contacts['contact_history'][-1]['loaded_case_faces'])
    tight, old, nominal = (rows[c] for c in (TIGHT, OLD, NOMINAL))
    assert tight['all_eight_force_screens_passed'] and nominal['all_eight_force_screens_passed']
    assert not old['all_eight_force_screens_passed']
    assert input_record(TIGHT)['reference_input_sha256'] == old['input_sha256']
    verdict = read(AUDIT / f'{TIGHT}_balance_verdict.json')
    verified(AUDIT / f'{TIGHT}_seats.json', verdict['seats_sha256'])
    verified(AUDIT / f'{TIGHT}_load_path.json', verdict['load_path_sha256'])
    assert verdict['locked_force_accepted'] and verdict['all_saved_force_screens_passed']
    fields_path = AUDIT / f'{TIGHT}_matched_fields.json'
    fields = read(fields_path)
    assert fields['reference'] == OLD and fields['reference_rst_sha256'] == old['rst_sha256']
    assert fields['control_rst_sha256'] == tight['rst_sha256']
    write_json(AUDIT / 'aluminium_cylinder_tolerance_comparison.json', dict(
        cases=rows, tighter_force_criterion_N=0.0001,
        tight_to_nominal_force_ratio=tight['locked_force_N']/nominal['locked_force_N'],
        matched_fields_sha256=digest(fields_path),
        tight_vs_old_cylinder_max_PCB_difference_um=fields['solids_at_lock']['PCB']['max_vector_difference_um'],
        conclusion='All eight tighter cylindrical equilibria pass the existing force screens. The final pocket force is about twice the balanced nominal quadratic model. Contact formulation sensitivity remains unresolved.',
        scope='Native ANSYS installation controls, independently audited. The old unbalanced cylinder result remains rejected. This comparison does not replace nominal vibration bases or establish physical contact/strength validation; no additional sweep is added.'))
    print('Cylindrical force', tight['locked_force_N'], 'N; balance', 100*tight['locked_relative_residual'], '%; nominal ratio', tight['locked_force_N']/nominal['locked_force_N'])

if __name__ == '__main__':
    run()

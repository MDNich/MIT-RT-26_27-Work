"""Compare both screw materials at the first saved loading of the fixed middle cell."""
import numpy as np

from audit_local import read
from compare_pull import series
from compare_snug_forward_mounts import OUTPUT as PREVIOUS
from film_identity import digest, write_json
from snug_directional_result import first_bracket, refined_tab_crossing
from stage_snug_fit import AUDIT

OUTPUT = AUDIT/'forward_middle_engagement_comparison.json'
STEMS = {m: f'snug125_{m}_lateral_friction_locked_pin1_m15_ls3_ss{s}'
         for m, s in (('nylon', 18), ('aluminium', 15))}


def compare():
    previous = read(PREVIOUS)
    records, pressures, mounts, targets, hashes = {}, {}, {}, {}, {}
    for material, stem in STEMS.items():
        paths = {key: AUDIT/f'{stem}_{suffix}.json' for key, suffix in
                 (('checkpoint', 'checkpoint'), ('pressure', 'cell_pressure'),
                  ('mounts', 'mount_reactions'), ('targets', 'fixed_targets'))}
        proof, pressure, mount, target = [read(p) for p in paths.values()]
        assert proof['input_sha256'] == previous['input_sha256'][material]
        for rec in (pressure, mount, target):
            assert rec['checkpoint_sha256'] == digest(paths['checkpoint'])
        assert proof['rst_sha256'] == pressure['rst_sha256'] == mount['rst_sha256']
        assert pressure['fixed_body_check_sha256'] == digest(paths['targets'])
        records[material] = proof
        pressures[material] = {r['native_set']: r for r in pressure['states']}
        mounts[material] = {r['native_set']: r for r in mount['states']}
        targets[material] = {r['native_set']: r['possible_target_bodies'] for r in target['loaded_states']}
        hashes[material] = {k: dict(path=str(p.relative_to(AUDIT.parent.parent)), sha256=digest(p))
                            for k, p in paths.items()}
    nylon = records['nylon']
    refined = refined_tab_crossing(nylon['case'], nylon['input_sha256'],
                                  {r['native_set']: r['travel_mm'] for r in nylon['states']})
    end = refined['native_set']-1
    assert end == max(pressures['nylon']) == 22
    bare, baseline = series(previous['bare_case'])
    assert bare['rst_sha256'] == previous['bare_rst_sha256']
    rows = []
    for a, b in zip(nylon['states'][:end], records['aluminium']['states'][:end], strict=True):
        assert a['native_set'] == b['native_set'] and a['loadstep'] == b['loadstep']
        assert abs(a['travel_mm']-b['travel_mm']) < 1e-10
        assert a['within_screens'] and b['within_screens']
        if a['loadstep'] != 3:
            continue
        rows.append(dict(travel_mm=a['travel_mm'], nylon=a, aluminium=b,
                         bare=first_bracket(baseline, 'ux_mm', a['travel_mm'], 1),
                         aluminium_to_nylon_force_ratio=b['cell_force_N']/a['cell_force_N']))
    assert rows[:-1] == previous['common_native_travel']
    assert len(rows) == 13 and abs(rows[-1]['travel_mm']-.219375) < 1e-10
    details = {}
    for material, states in records.items():
        k = rows[-1][material]['native_set']
        before, after = rows[-2][material], rows[-1][material]
        old = targets[material].get(k-1, {})
        new = targets[material][k]
        assert '19' not in old and '19' in new and set(new) <= {'19', '15'}
        assert all('19' not in g for j, g in targets[material].items() if j < k)
        for j in (k-1, k):
            pressure = pressures[material][j]
            state = states['states'][j-1]
            assert abs(pressure['travel_mm']-state['travel_mm']) < 1e-10
            assert pressure['actuator_N'] == state['cell_force_N']
            for body, target in targets[material].get(j, {}).items():
                np.testing.assert_allclose(pressure['cells'][body]['reaction_XYZ_N'], target['force_N'], atol=1e-6, rtol=1e-6)
        tab = mounts[material][k]
        assert tab['native_set'] == k
        details[material] = dict(
            native_set=k, travel_mm=after['travel_mm'], actuator_N=after['cell_force_N'],
            middle_cell_N=new['19']['force_N'][0],
            right_cell_N=new.get('15', {'force_N': [0.]})['force_N'][0],
            middle_contact_bracket_mm=[before['travel_mm'], after['travel_mm']],
            middle_contact_bracket_force_N=[before['cell_force_N'], after['cell_force_N']],
            case_mounts_N=after['screw_support_resistance_N'], nickel_clamps_N=after['nickel_clamp_resistance_N'],
            percent_applied_to_middle=100*new['19']['force_N'][0]/after['cell_force_N'],
            pressure=pressures[material][k]['cells'],
            peak_screw=max(tab['tabs'], key=lambda r: r['peak_shank_fibre_MPa']))
    result = dict(previous_comparison_sha256=digest(PREVIOUS), sources=hashes,
                  common_native_travel=rows, last_common_native_set=end, matched_endpoint=details,
                  refined_nylon_limit=refined, bare_case=previous['bare_case'], bare_rst_sha256=bare['rst_sha256'],
                  scope='Same native cell travel and sealed fixture geometry; only the screw material differs. '
                        'The fixed middle cell first carries load within the same saved interval for both mounts. '
                        'Comparison stops at the last station before the independently refined nylon coupon crossing. '
                        'The fixed neighbours and screw supports are local-fixture assumptions, not full-board behaviour. '
                        'The contact onset is bracketed, not an exact threshold; local pressure and stress need spatial convergence.')
    write_json(OUTPUT, result)
    print('Common endpoint:', {m: {k: d[k] for k in ('actuator_N', 'middle_cell_N', 'case_mounts_N', 'nickel_clamps_N')}
                               for m, d in details.items()})


if __name__ == '__main__':
    compare()

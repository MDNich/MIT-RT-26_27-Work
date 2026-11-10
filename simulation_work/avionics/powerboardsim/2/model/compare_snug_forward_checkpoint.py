"""Compare the first audited aluminium forward checkpoint to the same nylon and bare fixtures."""
import re

import numpy as np

from audit_local import ROOT, read
from compare_pull import series
from film_identity import digest, verified, write_json
from snug_directional_result import first_bracket
from stage_snug_fit import AUDIT, INPUTS


CHECKPOINTS = {
    'nylon': 'snug125_nylon_lateral_friction_locked_pin1_m15_ls3_ss12_checkpoint.json',
    'aluminium': 'snug125_aluminium_lateral_friction_locked_pin1_m15_ls3_ss7_checkpoint.json',
}
OUTPUT = AUDIT / 'forward_screw_checkpoint_comparison.json'


def compare():
    records = {key: read(AUDIT/name) for key, name in CHECKPOINTS.items()}
    bare_name = records['nylon']['bare_case']
    bare, baseline = series(bare_name)
    decks = {}
    profiles = {}
    for key, rec in records.items():
        assert not rec['completed'] and rec['bare_case'] == bare_name
        assert rec['bare_rst_sha256'] == bare['rst_sha256']
        assert not rec['first_print_crossings'] and rec['first_excluded_set'] is None
        deck = INPUTS/rec['case']/'model.inp'
        verified(deck, rec['input_sha256'])
        text = deck.read_text()
        # Geometry, preload, load increments, contact, PLA and nickel cards must agree.
        pattern = r'(?m)^MP,(EX|PRXY|DENS),851,([^\n]+)$'
        cards = dict(re.findall(pattern, text))
        assert set(cards) == {'EX', 'PRXY', 'DENS'}
        decks[key] = re.sub(pattern, r'MP,\1,851,SCREW_PROPERTY', text)
        profiles[key] = {name: float(value) for name, value in cards.items()}
    assert decks['nylon'] == decks['aluminium']
    expected = {'nylon': {'EX': 3000., 'PRXY': .39, 'DENS': 1.14e-9},
                'aluminium': {'EX': 69000., 'PRXY': .33, 'DENS': 2.7e-9}}
    for key in expected:
        for prop, value in expected[key].items():
            assert np.isclose(profiles[key][prop], value, rtol=1e-14, atol=0)
    rows = {key: [r for r in rec['states'] if r['loadstep'] == 3]
            for key, rec in records.items()}
    common = []
    for alu in rows['aluminium']:
        same = [r for r in rows['nylon'] if abs(r['travel_mm']-alu['travel_mm']) < 1e-10]
        assert len(same) == 1 and same[0]['within_screens'] and alu['within_screens']
        nylon = same[0]
        reference = first_bracket(baseline, 'ux_mm', alu['travel_mm'], 1)
        assert reference is not None
        common.append(dict(travel_mm=alu['travel_mm'], bare=reference,
                           nylon=nylon, aluminium=alu,
                           aluminium_to_nylon_force_ratio=alu['cell_force_N']/nylon['cell_force_N']))
    assert len(common) == 7
    # The first three exact common stations precede native pocket loading.
    for item in common[:3]:
        assert abs(item['nylon']['cell_force_N']-item['aluminium']['cell_force_N']) < 1e-8
        assert all(item[k]['both_contact_pairs']['861']['closed_faces'] == 0 for k in rows)
    target = baseline[-1]['cell_force_N']
    equal_load = {}
    for key, rec in records.items():
        supported = [dict(set=r['native_set'], ux_mm=r['travel_mm'], cell_force_N=r['cell_force_N'])
                     for r in rec['states'] if r['within_screens'] and r['loadstep'] >= 2]
        hit = first_bracket(supported, 'cell_force_N', target, 1)
        assert hit == rec['equal_bare_endpoint_load']['cased']
        equal_load[key] = hit
    result = dict(bare_case=bare_name, bare_rst_sha256=bare['rst_sha256'],
                  checkpoint_sha256={key: digest(AUDIT/name) for key, name in CHECKPOINTS.items()},
                  input_sha256={key: rec['input_sha256'] for key, rec in records.items()},
                  only_input_differences='Three material-851 screw cards: EX, PRXY, DENS.',
                  screw_properties_N_mm_tonne=profiles,
                  common_native_travel=common, bare_endpoint=baseline[-1], equal_load=equal_load,
                  scope='Native converged local-fixture states, with exact common cased travels. Bare values '
                        'at those travels and cased travel at 8.542 N are bracketed interpolations. '
                        'The aluminium checkpoint is incomplete; no rupture, fully coupled board, '
                        'or contact-mesh convergence claim is made.')
    write_json(OUTPUT, result)
    print('Verified', len(common), 'common native travels; final force ratio',
          common[-1]['aluminium_to_nylon_force_ratio'])


if __name__ == '__main__':
    compare()

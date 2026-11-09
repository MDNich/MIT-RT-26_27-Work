"""Compare the two flush installation attempts at native states with matching screw travel."""
import argparse
import re

import numpy as np

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from installation_material import PLA


def scoped_history(history):
    lock = max(row['native_set'] for row in history if row['loadstep'] == 2)
    rows = [r for r in history if r['native_set'] >= lock]
    assert rows[0]['travel_mm'] == 0 and np.all(np.diff([r['travel_mm'] for r in rows]) > 0)
    assert np.max(np.abs(np.array(rows[0]['bolt_N']) - 750)) < 1.
    accepted = []
    for r in rows:
        if any(r['material'][key]['peak'] >= limit for key, limit in PLA.items()):
            break
        if any(c['loaded_corner_pen_max'] * 1000 > (.015 if key == '853' else .05) for key, c in r['contact'].items()):
            break
        accepted.append(r)
    return accepted


def first_crossings(history):
    limits = {}
    previous = None
    for row in history:
        observations = {key: (value['peak'], PLA[key]) for key, value in row['material'].items()}
        observations.update({key + '_outside_2mm': (value['peak_over_2mm_away'], PLA[key])
                             for key, value in row['material'].items()})
        observations['hardware_penetration_um'] = (row['contact']['853']['loaded_corner_pen_max'] * 1.e6, 15.)
        for key, (value, limit) in observations.items():
            if key not in limits and value > limit:
                limits[key] = dict(previous_travel_mm=previous, first_above_mm=row['travel_mm'],
                                   native_set=row['native_set'], observed=value, reference=limit)
        previous = row['travel_mm']
    return limits


def metrics(row):
    hardware = row['contact']['853']
    return dict(native_set=row['native_set'], drive_N=row['drive_N'], total_drive_N=sum(row['drive_N']),
                loaded_hardware_faces=hardware['sliding'] + hardware['sticking'],
                max_loaded_hardware_penetration_um=hardware['loaded_corner_pen_max'] * 1e6,
                loaded_tab_faces=sum(v['sliding']+v['sticking'] for key,v in row['contact'].items() if key != '853'),
                peak_PLA_in_plane_tension_MPa=row['material']['in_plane_tension_MPa']['peak'],
                peak_PLA_through_layer_tension_MPa=row['material']['layer_tension_MPa']['peak'],
                maximum_screw_fibre_tension_MPa=row['maximum_screw_fibre_tension_MPa'],
                locked_bolt_force_N=row['bolt_N'])


def compare(nylon_checkpoint, aluminium_checkpoint, campaign):
    sources, decks, records = {}, {}, {}
    for metal, checkpoint in [('nylon', nylon_checkpoint), ('aluminium', aluminium_checkpoint)]:
        case = 'flush_' + metal + '_surf1_static'
        folder = ROOT / 'validation/partition_checks' / case
        path = folder / (checkpoint + '_history.json')
        audit = read(path)
        manifest_path = folder / (checkpoint + '_sources.json')
        verified(manifest_path, audit['manifest_sha256'])
        manifest = read(manifest_path)
        assert audit['case'] == manifest['case'] == case and audit['campaign'] == manifest['campaign'] == campaign
        assert len(audit['history']) == manifest['sets']
        verified(ROOT / 'validation/partition_checks/raised_partition_control.json', audit['control_sha256'])
        deck_path = ROOT / '.runtime/inputs' / case / 'model.inp'
        verified(deck_path, manifest['model_sha256'])
        material_cards = re.compile(rb'(?im)^MP,(EX|PRXY|DENS),851,([^\r\n]+)')
        deck = deck_path.read_bytes()
        cards = material_cards.findall(deck)
        assert len(cards) == 3 and {key for key,_ in cards} == {b'EX', b'PRXY', b'DENS'}
        decks[metal] = material_cards.sub(rb'MP,\1,851,SCREW_PROPERTY', deck)
        sources[metal] = dict(case=case, checkpoint=checkpoint, history_sha256=digest(path), source_sha256=digest(manifest_path),
                              deck_sha256=manifest['model_sha256'], screw_properties={k.decode(): float(v) for k,v in cards})
        sources[metal]['first_limit_crossings'] = first_crossings(audit['history'])
        records[metal] = scoped_history(audit['history'])
    assert decks['nylon'] == decks['aluminium']
    pairs = []
    for row in records['nylon']:
        matches = [r for r in records['aluminium'] if abs(r['travel_mm'] - row['travel_mm']) < 1.e-7]
        if not matches:
            continue
        other, = matches
        pairs.append(dict(travel_mm=row['travel_mm'], nylon=metrics(row), aluminium=metrics(other)))
    assert len(pairs) >= 2 and pairs[0]['travel_mm'] == 0.
    output = dict(campaign=campaign, sources=sources, common_states=pairs,
                  scope='Shared converged screw travels from the locked state up to the checked material and penetration '
                  'limits in both installations. The original inputs differ only in the four screw shank properties. '
                  'No interpolation between increments or estimate of full seating force.')
    out = ROOT / 'validation/installation_comparisons' / f'flush_{nylon_checkpoint}_{aluminium_checkpoint}.json'
    write_json(out, output)
    print(out.name, pairs[-1])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('nylon_checkpoint')
    p.add_argument('aluminium_checkpoint')
    p.add_argument('--campaign', default='nov08_01')
    a = p.parse_args()
    compare(a.nylon_checkpoint, a.aluminium_checkpoint, a.campaign)

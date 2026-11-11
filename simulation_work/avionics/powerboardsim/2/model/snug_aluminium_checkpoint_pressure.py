"""Recover driven and fixed-cell pressures from independent forces on audited aluminium checkpoints."""
import argparse
from hashlib import sha256
from pathlib import Path

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_pocket_faces import SIX
from snug_pull_pressure import (audit_face, contact_index, dpf_fields, loaded_faces,
                               summarize, target_owners, verify_saved_records)
from stage_snug_fit import AUDIT, MESH


CASE = 'snug125_aluminium_lateral_friction_locked_pin1_m15'
FOLDER = ROOT/'.runtime/qa/snug125/directional-readback'/CASE/'ls3_ss12'


def audit(folder=FOLDER):
    checkpoint = AUDIT/f'{CASE}_{folder.name}_checkpoint.json'
    proof = read(checkpoint)
    assert proof['case'] == CASE and not proof['completed']
    assert proof['first_excluded_set'] is None and not proof['first_print_crossings']
    fixed_path = AUDIT/f'{CASE}_{folder.name}_fixed_targets.json'
    fixed = read(fixed_path)
    assert fixed['checkpoint_sha256'] == digest(checkpoint)
    fixed_reference = {r['native_set']: r['possible_target_bodies'] for r in fixed['loaded_states']}
    skin = MESH/'fixture_targets_0005.npz'
    verified(skin, fixed['skin_sha256'])
    verified(folder/'pull.rst', proof['rst_sha256'])
    raw = reader.read_binary(folder/'pull.rst')
    owners = target_owners(raw, skin)
    fields = {861: dpf_fields(folder/'dpf_points', proof['rst_sha256'])}
    if fixed_reference:
        verified(folder/'dpf_fixed_faces/displacements.bin', fixed['DPF_displacements_sha256'])
        fields[862] = dpf_fields(folder/'dpf_fixed_faces', proof['rst_sha256'])
    index = contact_index(raw)
    errors = dict.fromkeys(('pressure_error_MPa', 'relative_area_error', 'virtual_work_relative_error'), 0.)
    states = []
    for row in proof['states']:
        k = row['native_set']
        if row['loadstep'] != 3:
            continue
        assert row['within_screens']
        grouped = {}
        signature = sha256()
        for element, native, stress, forces in loaded_faces(raw, index, k, signature):
            pair = element[2]
            nodes, displacement = fields[pair]
            face = element[10:18]
            assert face[2] == face[3] == face[6]
            xyz = raw.mesh.nodes[positions(raw.mesh.nnum, face[SIX])] + displacement[k][positions(nodes, face[SIX])]
            result = audit_face(native, stress, forces, xyz)
            targets = native[45:48][native[:3] >= 2]
            assert np.all((targets > 0) & (targets < 2**24) & (targets == targets.astype(int)))
            bodies = {owners[int(target)] for target in targets}
            assert len(bodies) == 1
            body = bodies.pop()
            assert (body == 4) == (pair == 861)
            grouped.setdefault(str(body), []).append(result)
            for key in errors:
                errors[key] = max(errors[key], result[key])
        cells = {key: summarize(faces) for key, faces in grouped.items()}
        reference = fixed_reference.get(k, {})
        assert set(cells)-{'4'} == set(reference)
        for body, data in reference.items():
            assert cells[body]['loaded_faces'] == data['faces']
            np.testing.assert_allclose(cells[body]['reaction_XYZ_N'], data['force_N'], rtol=1e-7, atol=1e-7)
        for pair in (861, 862):
            members = [g for key, g in cells.items() if (key == '4') == (pair == 861)]
            expected = row['both_contact_pairs'][str(pair)]
            assert sum(g['loaded_faces'] for g in members) == expected['closed_faces']
            force = sum((np.array(g['reaction_XYZ_N']) for g in members), np.zeros(3))
            np.testing.assert_allclose(force, expected['force_N'], rtol=1e-6, atol=1e-6)
        states.append(dict(native_set=k, travel_mm=row['travel_mm'], actuator_N=row['cell_force_N'],
                           cells=cells,
                           native_pressure_records_sha256=signature.hexdigest()))
    earlier = read(AUDIT/f'{CASE}_ls3_ss7_checkpoint.json')
    overlap = [r for r in states if r['native_set'] <= earlier['converged_sets']]
    verify_saved_records(folder.parent/'ls3_ss7/pull.rst', earlier['rst_sha256'], overlap)
    if folder.name != FOLDER.name:
        prior = read(AUDIT/f'{CASE}_{FOLDER.name}_cell_pressure.json')
        prior_checkpoint = AUDIT/f'{CASE}_{FOLDER.name}_checkpoint.json'
        verified(prior_checkpoint, prior['checkpoint_sha256'])
        assert proof['states'][:read(prior_checkpoint)['converged_sets']] == read(prior_checkpoint)['states']
        assert states[:len(prior['states'])] == prior['states']
        verify_saved_records(FOLDER/'pull.rst', prior['rst_sha256'], states[:len(prior['states'])])
    result = dict(case=CASE, rst_sha256=proof['rst_sha256'], checkpoint_sha256=digest(checkpoint),
                  fixed_body_check_sha256=digest(fixed_path), earlier_rst_crosscheck_sha256=earlier['rst_sha256'],
                  overlapping_pull_states=len(overlap), skin_sha256=fixed['skin_sha256'],
                  DPF_displacements_sha256=digest(folder/'dpf_points/displacements.bin'),
                  states=states, largest_face_errors=errors,
                  scope='Native frictionless contact quadrature on the 1.5 mm PLA mesh against the rigid left-cell skin. '
                        'Pressure and loaded area reconstructed from independent ENF virtual work and deformed face areas. '
                        'All supported checkpoint states are included; this does not establish spatial convergence or cell-wall strength.')
    if fixed_reference:
        result['fixed_DPF_displacements_sha256'] = digest(folder/'dpf_fixed_faces/displacements.bin')
        result['previous_pressure_audit_sha256'] = digest(AUDIT/f'{CASE}_{FOLDER.name}_cell_pressure.json')
        result['scope'] = ('Native frictionless quadrature on the 1.5 mm PLA mesh against the driven and fixed rigid cell skins. '
                           'Each loaded target ID agrees with an independent geometric body attribution. Pressure, area and nodal '
                           'virtual work are independently checked, with exact overlap against the earlier checkpoint. '
                           'Native material and contact screens pass; peak spatial convergence and actual cell strength remain unresolved.')
    write_json(AUDIT/f'{CASE}_{folder.name}_cell_pressure.json', result)
    print(errors, states[-1], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path, nargs='?', default=FOLDER)
    audit(parser.parse_args().folder)

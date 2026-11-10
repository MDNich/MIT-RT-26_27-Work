"""Recover driven-cell pressure from independent nodal forces on the audited aluminium checkpoint."""
from hashlib import sha256

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


def audit():
    checkpoint = AUDIT/f'{CASE}_{FOLDER.name}_checkpoint.json'
    proof = read(checkpoint)
    assert proof['case'] == CASE and not proof['completed']
    assert proof['first_excluded_set'] is None and not proof['first_print_crossings']
    fixed_path = AUDIT/f'{CASE}_{FOLDER.name}_fixed_targets.json'
    fixed = read(fixed_path)
    assert fixed['checkpoint_sha256'] == digest(checkpoint) and not fixed['loaded_states']
    skin = MESH/'fixture_targets_0005.npz'
    verified(skin, fixed['skin_sha256'])
    verified(FOLDER/'pull.rst', proof['rst_sha256'])
    raw = reader.read_binary(FOLDER/'pull.rst')
    owners = target_owners(raw, skin)
    nodes, fields = dpf_fields(FOLDER/'dpf_points', proof['rst_sha256'])
    index = contact_index(raw)
    errors = dict.fromkeys(('pressure_error_MPa', 'relative_area_error', 'virtual_work_relative_error'), 0.)
    states = []
    for row in proof['states']:
        k = row['native_set']
        if row['loadstep'] != 3:
            continue
        assert row['within_screens'] and row['both_contact_pairs']['862']['closed_faces'] == 0
        faces = []
        signature = sha256()
        for element, native, stress, forces in loaded_faces(raw, index, k, signature):
            assert element[2] == 861
            face = element[10:18]
            assert face[2] == face[3] == face[6]
            xyz = raw.mesh.nodes[positions(raw.mesh.nnum, face[SIX])] + fields[k][positions(nodes, face[SIX])]
            result = audit_face(native, stress, forces, xyz)
            targets = native[45:48][native[:3] >= 2]
            assert np.all((targets > 0) & (targets < 2**24) & (targets == targets.astype(int)))
            assert {owners[int(target)] for target in targets} == {4}
            faces.append(result)
            for key in errors:
                errors[key] = max(errors[key], result[key])
        reference = row['both_contact_pairs']['861']
        assert len(faces) == reference['closed_faces']
        force = np.sum([f['force'] for f in faces], axis=0) if faces else np.zeros(3)
        np.testing.assert_allclose(force, reference['force_N'], rtol=1e-6, atol=1e-6)
        states.append(dict(native_set=k, travel_mm=row['travel_mm'], actuator_N=row['cell_force_N'],
                           cells={'4': summarize(faces)} if faces else {},
                           native_pressure_records_sha256=signature.hexdigest()))
    earlier = read(AUDIT/f'{CASE}_ls3_ss7_checkpoint.json')
    overlap = [r for r in states if r['native_set'] <= earlier['converged_sets']]
    verify_saved_records(FOLDER.parent/'ls3_ss7/pull.rst', earlier['rst_sha256'], overlap)
    result = dict(case=CASE, rst_sha256=proof['rst_sha256'], checkpoint_sha256=digest(checkpoint),
                  fixed_body_check_sha256=digest(fixed_path), earlier_rst_crosscheck_sha256=earlier['rst_sha256'],
                  overlapping_pull_states=len(overlap), skin_sha256=fixed['skin_sha256'],
                  DPF_displacements_sha256=digest(FOLDER/'dpf_points/displacements.bin'),
                  states=states, largest_face_errors=errors,
                  scope='Native frictionless contact quadrature on the 1.5 mm PLA mesh against the rigid left-cell skin. '
                        'Pressure and loaded area reconstructed from independent ENF virtual work and deformed face areas. '
                        'All supported checkpoint states are included; this does not establish spatial convergence or cell-wall strength.')
    write_json(AUDIT/f'{CASE}_{FOLDER.name}_cell_pressure.json', result)
    print(errors, states[-1], flush=True)


if __name__ == '__main__':
    audit()

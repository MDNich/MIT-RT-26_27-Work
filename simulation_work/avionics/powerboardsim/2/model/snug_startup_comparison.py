"""Match the two startup trajectories and locate their crossing faces on the sealed contact fixtures."""
import re

from audit_local import read
from audit_snug_shell import surfaces
from case_stress import source
from film_identity import digest, verified, write_json
from snug_pocket_geometry import face_key
from stage_snug_fit import AUDIT, INPUTS


def cut_faces(spec):
    """Read the exact quadratic face selections passed to ESURF in the sealed APDL input."""
    path = INPUTS / spec['case'] / 'model.inp'
    verified(path, spec['input_sha256'])
    deck = path.read_text()
    skin = deck.split('real,31\n', 1)[1].split('cm,PBTOUCH,elem', 1)[0]
    body_for_element = {int(eid): int(mat) for mat, block in
                        re.findall(r'(?ms)^mat,(850|176|191)\n(.*?)(?=^mat,|^et,|\Z)', deck)
                        for eid in re.findall(r'(?m)^en,(\d+),', block)}
    faces = {int(mat): set() for mat in spec['material_sets']}
    for eid, selection in re.findall(r'(?m)^esel,s,elem,,(\d+)\nnsel,none\n((?:nsel,a,node,,\d+\n){6})esurf$', skin):
        nodes = [int(line.split(',')[-1]) for line in selection.splitlines()]
        faces[body_for_element[int(eid)]].add(face_key(nodes))
    assert sum(map(len, faces.values())) == skin.splitlines().count('esurf')
    for mat, keys in faces.items():
        assert len(keys) == spec['material_sets'][str(mat)]['exterior_faces']
    return faces


def compare(variant):
    cuts = read(AUDIT / (variant + '_patch_inputs.json'))
    shell_path = AUDIT / (variant + '_shell_inputs_v2.json')
    shell = read(shell_path)['shell_' + variant + '_contact_v2']
    preflight = read(AUDIT / (variant + '_shell_preflight_v2.json'))
    assert preflight['registry_sha256'] == digest(shell_path)
    static, _, rst = source(shell['static_case'], shell['campaign'])
    assert static['rst_sha256'] == shell['static_rst_sha256']
    # Parent ESURF has both triangular and quadrilateral targets.
    case_skin = {face_key(face): eid for face, eid in surfaces(rst, 853).items()}
    target_skin = {face_key(face) for face in surfaces(rst, 852) if len(face) == 6}
    installed = read(AUDIT / (variant + '_static_contacts.json'))
    assert installed['rst_sha256'] == static['rst_sha256']
    loaded = {eid for row in installed['contact_history'][-1]['loaded_case_faces'] for eid in row['element_ids']}
    loaded_keys = {key for key, eid in case_skin.items() if eid in loaded}
    assert len(loaded_keys) == len(loaded) > 0
    domains = {}
    cut_metadata = {}
    for radius in (9, 15):
        spec = cuts[f'patch_{variant}_Z_span{radius}_contact_v1']
        assert spec['parent_static_sha256'] == shell['static_rst_sha256']
        assert spec['parent_modal_sha256'] == shell['basis_rst_sha256']
        keys = cut_faces(spec)
        assert keys[850] <= case_skin.keys() and keys[176] | keys[191] <= target_skin
        domains[radius] = keys
        cut_metadata[radius] = dict(input_sha256=spec['input_sha256'],
                                    middle_loaded_faces_present=len(loaded_keys & keys[850]))
    assert all(domains[9][m] <= domains[15][m] for m in domains[9])
    records = {}
    for method in ('native', 'exact'):
        scan_path = AUDIT / f'{variant}_outer_onset_Z_{method}.json'
        witness_path = scan_path.with_name(scan_path.stem + '_witness.json')
        scan, witness = read(scan_path), read(witness_path)
        assert scan['basis_rst_sha256'] == shell['basis_rst_sha256']
        assert scan['method'] == witness['method'] == method and scan['variant'] == witness['variant'] == variant
        assert scan['window_sha256'] == shell['replay_window_sha256'] and scan['base_axis'] == 'Z'
        assert digest(scan_path) == witness['source_sha256']
        cells = {}
        for side, mat in (('left', 176), ('right', 187)):
            row, event = scan['cells'][side], witness['cells'][side]
            lo, hi = event['first_intersection_interval_ms']
            assert lo == 1000 * row['last_contiguous_clear_sample'] / scan['sample_rate_Hz']
            assert hi == 1000 * event['sample'] / scan['sample_rate_Hz'] and hi > lo and not row['unresolved_samples']
            case, cell = face_key(event['PLA_nodes']), face_key(event['cell_nodes'])
            assert case in case_skin and cell in target_skin
            coverage = {radius: dict(PLA=case in keys[850], cell=cell in keys.get(mat, set()))
                        for radius, keys in domains.items()}
            cells[side] = dict(time_interval_ms=[lo, hi], xyz_mm=event['quadratic_point_xyz_mm'],
                               cut_coverage=coverage, parent_PLA_element=case_skin[case])
        order = sorted(cells, key=lambda side: cells[side]['time_interval_ms'][0])
        assert cells[order[0]]['time_interval_ms'][1] < cells[order[1]]['time_interval_ms'][0]
        records[method] = dict(cells=cells, order=order, witness_sha256=digest(witness_path),
                               excitation_sha256=scan['input_sha256'], sample_rate_Hz=scan['sample_rate_Hz'])
    native, exact = records['native'], records['exact']
    assert native['order'] == exact['order'] and native['excitation_sha256'] == exact['excitation_sha256']
    assert native['sample_rate_Hz'] == exact['sample_rate_Hz']
    for side in native['cells']:
        n, e = [r['cells'][side]['time_interval_ms'] for r in (native, exact)]
        assert max(n[0], e[0]) <= min(n[1], e[1])
    return dict(variant=variant, installed_PLA_face_count=len(loaded_keys), cuts=cut_metadata,
                shell_registry_sha256=digest(shell_path), methods=records)


if __name__ == '__main__':
    write_json(AUDIT / 'startup_outer_comparison.json',
               dict(variants={mat: compare('snug125_' + mat) for mat in ('nylon', 'aluminium')},
                    scope='Sampled fixed-contact startup, native MCF and independent exact integration. '
                          'Face membership measures the coverage of existing fixture inputs.'))

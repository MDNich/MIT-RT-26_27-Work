"""Apply the existing force screens to the native cylindrical-surface control."""
import numpy as np

from case_stress import source
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_board_pull_seats import BearingSections, check_installation
from snug_board_pull import BODIES
from snug_preload_fields import differences, locked_fields
from snug_preload_load_path import audit as load_path
from stage_snug_fit import AUDIT, input_record

CASE = 'snug125_aluminium_cylinder_static'
REFERENCE = 'snug125_aluminium_out2_static'
CAMPAIGN = 'nov08_01'


def audit(case=CASE):
    assert case in (CASE, 'snug125_aluminium_cylinder_tol0001_static')
    reference_case = CASE if case.endswith('_tol0001_static') else REFERENCE
    spec, reference = map(input_record, (case, reference_case))
    assert spec['reference_input_sha256'] == reference['input_sha256']
    assert spec['mesh_sha256'] == reference['mesh_sha256']
    assert spec['supports'] == reference['supports']
    proof, folder, raw = source(case, CAMPAIGN)
    verified(folder / 'model.inp', spec['input_sha256'])
    sections = BearingSections(case.removesuffix('_static'), raw, (folder / 'model.inp').read_text())
    states, axial, vector, contacts = check_installation(case, sections)
    seats = AUDIT / (case + '_seats.json')
    write_json(seats, dict(case=case, rst_sha256=proof['rst_sha256'],
        input_sha256=spec['input_sha256'], native_contact_audit_sha256=digest(contacts),
        control_kind=('force tolerance with cylindrical corrections retained' if case != CASE else
                      'native cylindrical surface correction with unchanged mesh and Gauss detection'),
        states=states, states_outside_force_screens=[r['native_set'] for r in states if not r['within_force_screens']],
        max_axial_equilibrium_residual_N=axial, max_case_vector_residual_N=vector,
        scope='Unmodified four-tab and M4/spacer force screens at every saved installation state. '
              'Failed states remain diagnostic, including any final state.'))
    load_path(case)
    write_json(AUDIT / (case + '_balance_verdict.json'), dict(case=case,
        rst_sha256=proof['rst_sha256'], seats_sha256=digest(seats),
        load_path_sha256=digest(AUDIT / (case + '_load_path.json')),
        all_saved_force_screens_passed=all(r['within_force_screens'] for r in states),
        locked_force_accepted=states[-1]['within_force_screens'],
        locked_vector_residual_N=states[-1]['four_tab_force_balance_residual_N'],
        locked_relative_vector_residual=states[-1]['relative_vector_residual'],
        scope='Native solver completion and geometry audits alone do not accept the local pocket force. '
              'This verdict applies the original independent mounting-force screens.'))
    base, ids0, u0, record0 = locked_fields(reference_case)
    control, ids1, u1, record1 = locked_fields(case)
    regions = {'PCB': [208], 'cells': BODIES,
               'nickel_strips': [174, 179, 180, 186, 189, 193],
               'washers': [173, 178, 181, 182, 183, 192], 'printed_case': [850]}
    fields = {}
    for name, materials in regions.items():
        nodes = []
        for result in (base, control):
            grid = result.quadgrid
            take = np.isin(grid.cell_data['ansys_elem_type_num'], [185, 186, 187]) & np.isin(
                grid.cell_data['ansys_material_type'], materials)
            nodes.append(np.unique(grid.extract_cells(take).point_data['ansys_node_num']))
        ids, check = nodes
        np.testing.assert_array_equal(ids, check)
        xyz = base.mesh.nodes[positions(base.mesh.nnum, ids)]
        np.testing.assert_allclose(xyz, control.mesh.nodes[positions(control.mesh.nnum, ids)], rtol=0, atol=1e-12)
        fields[name] = differences(ids, xyz * 1000, u0[positions(ids0, ids)], u1[positions(ids1, ids)])
    write_json(AUDIT / (case + '_matched_fields.json'), dict(case=case, reference=reference_case,
        reference_rst_sha256=record0['source_rst_sha256'], control_rst_sha256=record1['source_rst_sha256'],
        reference_native_U_sha256=record0['native_DPF_U_sha256'], control_native_U_sha256=record1['native_DPF_U_sha256'],
        force_seats_sha256=digest(seats), solids_at_lock=fields,
        scope='Native displacement vectors at identical nodes and reference positions, at final bolt lock. '
              'These kinematic differences do not waive the force screens.'))
    print('Cylinder force screens', [r['within_force_screens'] for r in states], flush=True)
    print('Locked displacement differences [um]', {k: v['max_vector_difference_um'] for k, v in fields.items()}, flush=True)


if __name__ == '__main__':
    audit()

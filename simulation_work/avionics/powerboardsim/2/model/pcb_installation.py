"""Recover PCB bending during the supported part of an attempted flush case installation."""
import argparse
import re

import numpy as np

from audit_local import ROOT, read, table
from dpf_readback import export
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from native_rst import read_rst


def signed_corners(rst, elements, native_set, field, width):
    enum, values, nodes = rst.element_solution_data(native_set - 1, field)
    ix = positions(enum, elements)
    corners = np.concatenate([nodes[j] for j in ix])
    counts = np.array([len(nodes[j]) for j in ix])
    data = np.concatenate([values[j].reshape(n, width) for j, n in zip(ix, counts, strict=True)])
    assert np.isfinite(data).all()
    return np.repeat(elements, counts), corners, data


def maximum_principal_strain(engineering):
    tensor = np.zeros((len(engineering), 3, 3), dtype=float)
    tensor[:, [0, 1, 2], [0, 1, 2]] = engineering[:, :3]
    tensor[:, [1, 2, 2], [0, 1, 0]] = .5 * engineering[:, 3:6]
    return np.linalg.eigvalsh(tensor, UPLO='L')[:, -1]


def surface_strain(rst, elements, native_set, modulus, nu, zlimits):
    numbers, corners, stress = signed_corners(rst, elements, native_set, 'ENS', 6)
    en, cn, native = signed_corners(rst, elements, native_set, 'EEL', 7)
    assert np.array_equal(en, numbers) and np.array_equal(cn, corners)
    computed = np.empty_like(stress, dtype=float)
    computed[:, :3] = ((1 + nu) * stress[:, :3] - nu * stress[:, :3].sum(1)[:, None]) / modulus
    computed[:, 3:] = 2 * (1 + nu) / modulus * stress[:, 3:]
    error = np.linalg.norm(computed - native[:, :6], axis=0) / np.linalg.norm(native[:, :6], axis=0)
    assert error.max() < 1.e-4, error
    xyz = rst.mesh.nodes[positions(rst.mesh.nnum, corners)]
    peaks = {}
    for side, height in zip(('low_Z', 'high_Z'), zlimits, strict=True):
        rows = np.flatnonzero(np.isclose(xyz[:, 2], height, rtol=0, atol=1.e-9))
        strain = native[rows, :6]
        principal = maximum_principal_strain(strain)
        i = np.argmax(principal)
        j = rows[i]
        peaks[side] = dict(unaveraged_corners=len(rows), peak_principal_tensile_microstrain=float(principal[i] * 1.e6),
                           element=int(numbers[j]), node=int(corners[j]), xyz_mm=(1000 * xyz[j]).tolist())
    return peaks, error.tolist()


def audit(case, campaign, checkpoint, plot=False):
    folder = ROOT / '.runtime/archive' / campaign / case
    receipts = ROOT / '.runtime/receipts' / campaign / case
    ledger = read(receipts / 'archived.json')
    assert (receipts / 'released.txt').is_file() and (ledger['case'], ledger['campaign']) == (case, campaign)
    hashes = {item['name']: item['sha256'] for item in ledger['files']}
    for name in ('file.rst', 'model.inp', 'board_drives.csv'):
        verified(folder / name, hashes[name])
    rst = read_rst(folder / 'file.rst')
    deck = (folder / 'model.inp').read_text()
    def property_value(name):
        (value,) = re.findall('(?im)^MP,' + name + r',208,([^,\r\n]+)', deck)
        return float(value)
    modulus, nu = property_value('EX'), property_value('NUXY')

    material_path = ROOT / 'validation/installation_material' / (case + '.json')
    material = read(material_path)
    assert material['case'] == case and material['rst_sha256'] == hashes['file.rst']
    snapshot = ROOT / '.runtime/partition_snapshots' / campaign / case / checkpoint
    checkpoint_sha = digest(snapshot / 'receipts.json')
    manifest = read(snapshot / 'receipts.json')
    assert (manifest['case'], manifest['campaign'], manifest['model_sha256']) == (case, campaign, hashes['model.inp'])
    checks = ROOT / 'validation/partition_checks' / case
    history_path = checks / (checkpoint + '_history.json')
    gap_path = checks / (checkpoint + '_gap.json')
    hist, gaps = read(history_path), read(gap_path)
    assert hist['manifest_sha256'] == gaps['checkpoint_sha256'] == checkpoint_sha
    levels = {row['native_set']: row for row in material['history']}
    first = min((x['native_set'] for k, x in material['first_reference_crossings'].items() if k.startswith('all_')),
                default=rst.nsets + 1)
    history = []
    lock = max(row['native_set'] for row in hist['history'] if row['loadstep'] == 2)
    for row in hist['history']:
        k = row['native_set']
        if k < lock:
            continue
        assert row['loadstep'] == rst._resultheader['ls_table'][k-1, 0] and abs(row['time'] - rst.time_values[k-1]) < 1.e-8
        assert abs(levels[k]['travel_mm'] - row['travel_mm']) < 1.e-6
        if k >= first or any(1000 * c['loaded_corner_pen_max'] > (.015 if pair == '853' else .05)
                             for pair, c in row['contact'].items()):
            break
        history.append(row)
    sets = [row['native_set'] for row in history]
    assert len(sets) >= 2 and sets == list(range(lock, lock + len(sets)))
    complete = export(case, campaign, sets)
    subset = ROOT / '.runtime/post' / campaign / case / 'partition_DPF' / checkpoint
    request = read(subset / 'request.json')
    assert request['source_sha256'] == checkpoint_sha
    independent_ids = np.array(request['nodes'])
    verified(subset / 'displacements.bin', gaps['DPF_sha256'])
    check_u = np.fromfile(subset / 'displacements.bin', '<f8').reshape(len(request['sets']), len(independent_ids), 3)
    drives = table(folder / 'board_drives.csv')
    grid = rst.quadgrid
    mask = grid.cell_data['ansys_material_type'] == 208
    assert set(grid.cell_data['ansys_elem_type_num'][mask]) <= {185, 186, 187}
    board = grid.extract_cells(mask)
    ids = np.unique(board.point_data['ansys_node_num'])
    elements = np.sort(board.cell_data['ansys_elem_num'])
    xyz = rst.mesh.nodes[positions(rst.mesh.nnum, ids)]
    zlimits = [xyz[:, 2].min(), xyz[:, 2].max()]
    fixed = np.sort(rst.mesh.node_components['_FIXEDSU'])
    results = []
    relative_error = []
    last_shape = None
    for k, row in zip(sets, history, strict=True):
        stem = complete / f'set_{k:04d}'
        numbers = np.fromfile(stem.with_suffix('.ids'), '<i4')
        ix = np.argsort(numbers)
        numbers = numbers[ix]
        u = np.fromfile(stem.with_suffix('.u'), '<f8').reshape(-1, 3)[ix]
        independent = check_u[request['sets'].index(k)]
        discrepancy = float(abs(u[positions(numbers, independent_ids)] - independent).max())
        assert discrepancy < 1.e-9 and abs(u[positions(numbers, fixed)]).max() < 1.e-11
        native = drives[drives['set'] == k]
        assert np.array_equal(native['foot'], range(4))
        for pilots, field in [(np.arange(960101, 960105), 'board_z_m'), (np.arange(950002, 950010, 2), 'head_z_m')]:
            assert np.allclose(u[positions(numbers, pilots), 2], native[field], rtol=0, atol=1.e-10)
        xyz_u = u[positions(numbers, ids)]
        board_z = native['board_z_m'] * 1000
        head_z = native['head_z_m'] * 1000
        if k == lock:
            original = xyz_u.copy()
            board_lock = board_z.copy()
            head_lock = head_z.copy()
        board_travel = board_z - board_lock
        head_travel = head_z - head_lock
        assert np.allclose(head_travel - board_travel, row['travel_mm'], rtol=0, atol=2.e-8)
        last_shape = 1000 * (xyz_u[:, 2] - original[:, 2])
        low, high = int(last_shape.argmin()), int(last_shape.argmax())
        peaks, error = surface_strain(rst, elements, k, modulus, nu, zlimits)
        relative_error.append(error)
        results.append(dict(native_set=k, travel_mm=row['travel_mm'],
                            min_incremental_Z_mm=float(last_shape[low]), min_node=int(ids[low]), min_xyz_mm=(xyz[low] * 1000).tolist(),
                            max_incremental_Z_mm=float(last_shape[high]), max_node=int(ids[high]), max_xyz_mm=(xyz[high] * 1000).tolist(),
                            PCB_peak_total_displacement_mm=float(1000 * np.linalg.norm(xyz_u, axis=1).max()),
                            bearing_delta_Z_mm=board_travel.tolist(), drive_node_delta_Z_mm=head_travel.tolist(),
                            surfaces=peaks, max_split_combined_displacement_error_m=discrepancy,
                            displacement_sha256=digest(stem.with_suffix('.u')), node_ids_sha256=digest(stem.with_suffix('.ids'))))
    proof = dict(case=case, campaign=campaign, rst_sha256=hashes['file.rst'], input_sha256=hashes['model.inp'],
                 drive_table_sha256=hashes['board_drives.csv'], partition_history_sha256=digest(history_path),
                 partition_displacements_sha256=gaps['DPF_sha256'], comparison_nodes=len(independent_ids),
                 material_audit_sha256=digest(material_path), PCB_nodes=len(ids), PCB_elements=len(elements),
                 modulus_Pa=modulus, Poisson_ratio=nu, peak_component_constitutive_relative_L2=np.max(relative_error, axis=0).tolist(),
                 history=results, scope='Static PCB movement from six-bolt lock and total maximum principal elastic strain '
                 'on each exterior board plane during the verified installation prefix. Strains include preload. '
                 'The modeled homogeneous board provides no solder-joint or laminate failure allowable.')
    write_json(ROOT / 'validation/pcb_installation' / (case + '.json'), proof)
    if plot:
        draw(rst, ids, last_shape, results, case)
    return proof


def draw(rst, ids, delta_z, results, case):
    from report_plot import plt
    from matplotlib.collections import PolyCollection
    from clearance_response import surface

    mesh, faces, numbers, _ = surface(rst, [208])
    xyz_mm = mesh.points * 1000
    top = np.all(np.isclose(xyz_mm[faces, 2], xyz_mm[:, 2].max(), atol=1.e-6, rtol=0), axis=1)
    triangles = faces[top]
    assert len(triangles)
    towards_cells = -delta_z[positions(ids, numbers)]
    fig, (plan, trace) = plt.subplots(1, 2, figsize=(7.8, 2.35), layout='constrained')
    colors = PolyCollection(xyz_mm[triangles][:, :, [1, 0]], array=towards_cells[triangles].mean(1),
                            cmap='viridis', rasterized=True, edgecolors='none', antialiaseds=False)
    plan.add_collection(colors)
    plan.autoscale()
    plan.set_aspect('equal')
    plan.set(xlabel='Board Y [mm]', ylabel='Board X [mm]')
    fig.colorbar(colors, ax=plan, pad=.025, shrink=.88, aspect=20, label='Toward cells [mm]')
    travel = [r['travel_mm'] for r in results]
    traces = trace.plot(travel, -np.array([r['bearing_delta_Z_mm'] for r in results]), color='#3C78D8', lw=1.2)
    traces[0].set_label('Four PCB screw bearings')
    trace.plot(travel, [-r['min_incremental_Z_mm'] for r in results], color='#08357E', marker='o', ms=3,
               label='Maximum anywhere on PCB')
    trace.set(xlabel='Relative screw travel [mm]', ylabel='Toward cells [mm]')
    trace.legend(frameon=False, fontsize=8)
    for ax in (plan, trace):
        ax.spines[['top', 'right']].set_visible(False)
        ax.tick_params(labelsize=8)
    trace.grid(axis='y', alpha=.2)
    fig.savefig(ROOT / 'docs/figures' / (case + '-pcb-installation.pdf'), dpi=240, bbox_inches='tight', pad_inches=.06,
                metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('case')
    p.add_argument('checkpoint')
    p.add_argument('--campaign', default='nov08_01')
    p.add_argument('--plot', action='store_true')
    a = p.parse_args()
    result = audit(a.case, a.campaign, a.checkpoint, a.plot)
    print(result['history'][-1])

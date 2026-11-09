"""Recheck raised-case clearances at two signed base-X states on curved native element surfaces."""
import sys

import numpy as np

from audit_local import ROOT, read
from basis_comparison import field_files
from film_identity import digest, verified, write_json
from native_rst import read_rst
from seeded_motion import FS, integrate, participation


def contact_solids(rst):
    g = rst.quadgrid
    solid = np.isin(g.cell_data['ansys_elem_type_num'], [185, 186, 187])
    return [g.extract_cells(solid & np.isin(g.cell_data['ansys_material_type'], mats))
              for mats in ([850], [176, 187, 191])]


def set_coordinates(groups, ids, coordinates_m):
    for group in groups:
        nodes = group.point_data['ansys_node_num']
        select = np.searchsorted(ids, nodes)
        assert np.array_equal(ids[select], nodes)
        group.points = coordinates_m[select]
        group.point_data['coordinates'] = group.points.astype(np.float64)


def curved_skins(groups, level):
    skins = [group.extract_surface(nonlinear_subdivision=level, algorithm='dataset_surface').triangulate()
             for group in groups]
    for surface in skins:
        surface.points = surface.point_data['coordinates']
        assert surface.n_open_edges == 0
    return skins


def sampled_clearance(groups, ids, coordinates_m, levels):
    set_coordinates(groups, ids, coordinates_m)
    records = {}
    for level in levels:
        cap, cells = curved_skins(groups, level)
        _, count = cap.collision(cells, contact_mode=1, box_tolerance=0., cell_tolerance=0.)
        sd = cells.compute_implicit_distance(cap).point_data['implicit_distance'] * 1000
        assert np.isfinite(sd).all()
        records[level] = dict(PLA_triangles=cap.n_cells, cell_triangles=cells.n_cells,
                              intersect=bool(count), minimum_signed_vertex_gap_mm=float(sd.min()))
    return records


def run(variant, campaign):
    basis = variant + '_basis'
    vault = ROOT / '.runtime/archive' / campaign / basis
    proof = read(ROOT / 'validation/global' / f'{basis}.json')
    peak_path = ROOT / 'validation/peak_contact' / f'{variant}.json'
    search_path = ROOT / 'validation/clearance_rms' / f'{basis}.json'
    peak, search = read(peak_path), read(search_path)
    assert campaign == proof['campaign'] == peak['campaign'] == search['campaign']
    assert proof['rst_sha256'] == peak['basis_sha256'] == search['rst_sha256']
    verified(vault / 'file.rst', proof['rst_sha256'])
    ledger = read(ROOT / '.runtime/receipts' / campaign / basis / 'archived.json')
    verified(vault / 'solve.out', next(f['sha256'] for f in ledger['files'] if f['name'] == 'solve.out'))
    rst = read_rst(vault / 'file.rst')
    approach = search['scopes']['cells']['directions']['X']['seed_screen']
    times = np.array([approach['most_approached_sample_s'], peak['time_s']])
    indices = np.rint(times * FS).astype(int)
    log = (vault / 'solve.out').read_text(errors='replace')
    actual, q, _ = integrate(rst.time_values, participation(log, 'X'), 'X', indices)
    assert np.array_equal(actual, times)
    groups = contact_solids(rst)
    ids = np.unique(np.concatenate([group.point_data['ansys_node_num'] for group in groups]))
    xyz = rst.mesh.nodes[np.searchsorted(rst.mesh.nnum, ids)]
    assert np.array_equal(rst.mesh.nnum[np.searchsorted(rst.mesh.nnum, ids)], ids)
    displacement = np.zeros((len(q), len(ids), 3))
    for k, src in field_files(basis, campaign, proof['rst_sha256'], rst.nsets).items():
        nodes = np.fromfile(src.with_suffix('.ids'), '<i4')
        values = np.fromfile(src.with_suffix('.u'), '<f8').reshape(-1, 3)
        order = np.argsort(nodes)
        select = order[np.searchsorted(nodes[order], ids)]
        assert np.array_equal(nodes[select], ids)
        displacement += q[:, k-1, None, None] * values[select]

    records = {}
    for name, move in zip(('tightened', 'largest_approach', 'peak_layer_tension'),
                          (np.zeros_like(displacement[0]), *displacement), strict=True):
        records[name] = sampled_clearance(groups, ids, xyz+move, (1,2,3))
        print(variant, name, records[name], flush=True)
    assert not any(r['intersect'] for r in records['tightened'].values())
    for name, old in [('largest_approach', approach['maximum_target_vertex_depth_in_PLA_mm']),
                      ('peak_layer_tension', peak['peak']['deepest_sampled_cell_vertex_mm'])]:
        # First reproduce the existing midside-node comparison before interpreting finer skins.
        assert abs(records[name][1]['minimum_signed_vertex_gap_mm'] + old) < .0001
    write_json(ROOT / 'validation/curved_contact' / f'{variant}.json', dict(
        case=variant, campaign=campaign, basis_RST_sha256=proof['rst_sha256'],
        approach_audit_sha256=digest(search_path), peak_tension_audit_sha256=digest(peak_path),
        times_s=dict(largest_approach=float(times[0]), peak_layer_tension=float(times[1])), states=records,
        scope='Independent signed base-X history on the tightened native geometry. Each level subdivides the '
              'same deformed quadratic elements. Signed distances sample cell vertices against the closed PLA '
              'surface. Negative values and a triangle intersection indicate loss of the open-gap assumption.'))


if __name__ == '__main__':
    run(*sys.argv[1:])

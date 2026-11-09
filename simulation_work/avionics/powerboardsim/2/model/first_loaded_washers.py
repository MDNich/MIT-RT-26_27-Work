"""Locate the first native contact reactions on the fixed targets in the local flush installation."""
import numpy as np
import pyvista as pv
from ansys.mapdl import reader

from audit_local import ROOT, read, table
from film_identity import digest, verified, write_json
from tab_seating import point_fields


def run():
    case = 'flush_nylon_lateral_friction_locked_approach1'
    parent_path = ROOT / 'validation/partial_local' / f'{case}.json'
    parent = read(parent_path)
    campaign = parent['campaign']
    d = ROOT / '.runtime/archive' / campaign / case
    ledger = read(ROOT / '.runtime/receipts' / campaign / case / 'archived.json')
    assert ledger['case'] == case and ledger['campaign'] == campaign
    hashes = {f['name']:f['sha256'] for f in ledger['files']}
    assert hashes['pull.rst'] == parent['rst_sha256']
    for name in ('pull.rst', 'model.inp', 'case_pairs.csv'):
        verified(d / name, hashes[name])
    assert 'D,959001,ALL,0' in (d / 'model.inp').read_text().upper()
    onset = parent['contact_onset']['862']
    k = onset['native_set']
    reference = table(d / 'case_pairs.csv')
    ref = reference[(reference['set'] == k) & (reference['pair'] == 862)]
    assert len(ref) == 1 and np.all(reference['closed'][reference['set'] < k] == 0)
    rst = reader.read_binary(str(d / 'pull.rst'))
    ids, values, corners = rst.element_solution_data(k-1, 'EMN')
    assert (np.diff(ids) > 0).all()
    cells = rst.grid.cell_data
    use = (cells['ansys_real_constant'] == 862) & (cells['ansys_etype'] == 862)
    faces = cells['ansys_elem_num'][use]
    loaded = {}
    forces = {}
    for elem in faces:
        i = np.searchsorted(ids, elem)
        assert ids[i] == elem
        data = values[i]
        if data is not None and len(data) and data[40] in (2, 3):
            nodes = corners[i]
            assert len(nodes) == 4
            touching = np.unique(nodes[np.isin(data[:4], [2,3])])
            assert len(touching)
            loaded[int(elem)] = touching
            forces[int(elem)] = data[42:45].astype(float)
    assert len(loaded) == int(ref['closed'][0])
    total = np.sum(list(forces.values()), axis=0)
    assert np.allclose(total, [ref['f'+a+'_N'][0] for a in 'xyz'], atol=2e-5, rtol=3e-6)
    numbers, field = point_fields(rst, [k], np.concatenate(list(loaded.values())),
                                   field_directory='first_loaded_corners_v1')
    unique = np.unique(np.concatenate(list(loaded.values())))
    nnum = rst.mesh.nnum
    xyz = rst.mesh.nodes[np.searchsorted(nnum, unique)] + field[0, np.searchsorted(numbers, unique)]
    assert np.array_equal(nnum[np.searchsorted(nnum, unique)], unique)

    triangles = []
    pilots = []
    for el in rst.mesh.elem:
        if el[1] == 861 and el[2] == 862:
            nodes = np.unique(el[10:][el[10:] > 0])
            if el[7] == 99:
                pilots.append(int(el[10]))
            else:
                assert el[7] == 6 and len(nodes) == 3
                triangles.append(el[10:13])
    assert pilots == [959001]
    targets = pv.PolyData.from_regular_faces(rst.mesh.nodes, np.searchsorted(nnum, triangles)).clean()
    assert targets.n_cells == len(triangles)
    parts = targets.split_bodies()
    assert len(parts) == 8
    geom = read(ROOT / 'validation/rigid_case_drawdown.json')
    available = {r['STEP_body']: np.array(r['STEP_centre_mm']) for r in geom['records']
                 if r['STEP_body'] in (15,19,1,6,9,10,11,20)}
    target_ids, distances = [], []
    for b in parts:
        centroid = np.array(b.center)
        tag = min(available, key=lambda key: np.linalg.norm(centroid-available[key]))
        assert np.linalg.norm(centroid-available[tag]) < .2
        target_ids.append(tag)
        _, closest = b.find_closest_cell(xyz, return_closest_point=True)
        distances.append(np.linalg.norm(closest-xyz, axis=1))
    assert set(target_ids) == set(available)
    distances = np.array(distances).T
    rank = np.argsort(distances, axis=1)
    nearest = np.array(target_ids)[rank[:, 0]]
    ordered = np.take_along_axis(distances,rank,axis=1)
    assert ordered[:, 0].max() < .05 and (ordered[:, 1]-ordered[:, 0]).min() > .1
    reactions = {}
    for elem, nodes in loaded.items():
        tags = np.unique(nearest[np.searchsorted(unique, nodes)])
        assert len(tags) == 1
        tag = int(tags[0])
        reactions.setdefault(tag, []).append(forces[elem])
    audit = {tag:dict(faces=len(fs), contact_force_N=np.sum(fs, axis=0).tolist()) for tag, fs in reactions.items()}
    write_json(ROOT / 'validation/pulls/flush_first_contacts.json', dict(case=case, campaign=campaign,
        parent_audit_sha256=digest(parent_path), rst_sha256=parent['rst_sha256'], native_set=k,
        travel_bracket_mm=onset['top_travel_bracket_mm'], closed_faces=len(loaded), distinct_closed_corner_nodes=len(unique),
        greatest_distance_to_assigned_surface_mm=float(ordered[:,0].max()),
        minimum_separation_from_alternative_assignment_mm=float((ordered[:,1]-ordered[:,0]).min()),
        per_STEP_body=audit, combined_reaction_N=total.tolist(),
        scope='First saved loaded state. Positions are native DPF displacements plus initial coordinates. Each '
              'closed facet was assigned to the nearest actual rigid target patch at its loaded corners; the '
              'native element force sum matches POST1. The model has rigid neighboring hardware.'))
    print(audit)


if __name__ == '__main__':
    run()

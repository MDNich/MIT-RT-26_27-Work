"""Locate a printed-PLA coupon crossing on the native tetrahedra and the registered STEP tab."""
import argparse
from pathlib import Path

import gmsh
import numpy as np
from ansys.mapdl import reader
from scipy.spatial import cKDTree

from audit_local import read
from case_stress import corners
from film_identity import digest, verified, write_json
from installation_material import PLA
from local_equilibrium import positions
from snug_mount_reactions import ring_nodes
from stage_snug_fit import AUDIT, BEARINGS, INPUTS, MESH, SPACING, STEP, STEP_HASH


def local_points(points):
    return np.column_stack((34.6075 + points[:, 0], 60.3885 + points[:, 2],
                            -.55118 - 10 - SPACING - points[:, 1]))


def native_geometry(raw, mesh, deck):
    offset = 2100001
    tetra = mesh['tets']
    ids = 1200001 + np.arange(len(tetra))
    native = [e for e in raw.mesh.elem if e[1] == 850]
    native.sort(key=lambda e: e[8])
    assert np.array_equal(ids, [e[8] for e in native])
    assert np.array_equal(np.stack([e[10:20] for e in native]),
                          offset + tetra[:, [0,1,2,3,4,5,6,7,9,8]])
    node_ids = offset + np.arange(len(mesh['points']))
    xyz = raw.mesh.nodes[positions(raw.mesh.nnum, node_ids)]
    assert np.max(abs(xyz-local_points(mesh['points']))) < 1.e-7
    rings, _ = ring_nodes(deck)
    tied = np.concatenate(list(rings.values()))
    tied_tree = cKDTree(xyz[positions(node_ids, tied)])
    return ids, node_ids, xyz, tied_tree


def step_faces():
    verified(STEP, STEP_HASH)
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        vol, = gmsh.model.occ.importShapes(str(STEP))
        gmsh.model.occ.synchronize()
        faces = gmsh.model.getBoundary([vol], oriented=False)
        return {i: gmsh.model.getType(2, i) for d, i in faces if d == 2}
    finally:
        gmsh.finalize()


def summary(field, name, nodes, solids, node_ids, xyz, tied, mesh, types):
    values = field.reshape(-1, 4)
    idx = int(field.argmax())
    node = int(nodes.ravel()[idx])
    xyz_peak = xyz[positions(node_ids, [node])[0]]
    coincident = values[nodes == node]
    cutoff = PLA[name]
    hits = np.flatnonzero(field >= cutoff)
    winners = nodes.ravel()[hits]
    exceedances = []
    for hit in hits:
        n = int(nodes.ravel()[hit])
        location = xyz[positions(node_ids, [n])[0]]
        faces = [i for i in types if np.any(mesh[str(i)] == n-node_ids[0])]
        exceedances.append(dict(node=n, element=int(solids[hit//4]), value=float(field[hit]),
                                xyz_mm=location.tolist(), faces=faces,
                                tied_node_distance_mm=float(tied.query(location)[0])))
    ip = node-node_ids[0]
    owners = [i for i in types if np.any(mesh[str(i)] == ip)]
    return dict(corners_reaching_reference=exceedances, peak=float(field[idx]), element=int(solids[idx//4]), node=node,
                xyz_mm=xyz_peak.tolist(), faces={str(i):types[i] for i in owners},
                bearing_faces=[i for i in BEARINGS if i in owners], tied_node_distance_mm=float(tied.query(xyz_peak)[0]),
                incident_tetrahedra=len(coincident), incident_min=float(coincident.min()),
                incident_max=float(coincident.max()), incident_mean=float(coincident.mean()),
                corners_at_reference=len(winners), unique_nodes_at_reference=len(np.unique(winners)),
                elements_any_corner_at_reference=int((values.max(1) >= cutoff).sum()),
                elements_all_corners_at_reference=int((values.min(1) >= cutoff).sum()),
                highest_element_minimum=float(values.min(1).max()))


def analyse(folder):
    case = read(folder/'capture.json')['case']
    audit_path = AUDIT/f'{case}_{folder.name}_checkpoint.json'
    record = read(audit_path)
    verified(folder/'pull.rst', record['rst_sha256'])
    spec = read(AUDIT/'local_inputs_m15.json')[case]
    assert record['case'] == case and spec['input_sha256'] == record['input_sha256']
    meshfile = MESH/'case_1.5.npz'
    verified(meshfile, spec['mesh_sha256'])
    deck = INPUTS/case/'model.inp'
    verified(deck, spec['input_sha256'])
    raw = reader.read_binary(folder/'pull.rst')
    types = step_faces()
    with np.load(meshfile) as archive:
        mesh = {k:archive[k] for k in archive.files}
    solids, node_ids, xyz, tied = native_geometry(raw, mesh, deck.read_text())
    end = record['first_excluded_set'] or record['converged_sets']
    rows = []
    for station in (end-1, end):
        state = record['states'][station-1]
        n, s = corners(raw, station-1, 'ENS', solids, 6)
        en, eps = corners(raw, station-1, 'EEL', solids, 7)
        assert np.array_equal(n, en) and np.array_equal(n.reshape(-1, 4), node_ids[mesh['tets'][:, :4]])
        x, y, z, xy = s[:, :4].T
        fields = {'in_plane_tension_MPa': .5*(x+y) + np.hypot(.5*(x-y), xy),
                  'layer_tension_MPa': z, 'layer_tensile_strain': eps[:, 2]}
        result = {name:summary(field, name, n.reshape(-1, 4), solids, node_ids, xyz, tied, mesh, types)
                  for name, field in fields.items()}
        for name, component in result.items():
            assert abs(100*component['peak']/PLA[name] - state['printed_coupon_percent'][name]) < 1.e-6
        rows.append(dict(native_set=station, travel_mm=state['travel_mm'], cell_force_N=state['cell_force_N'],
                         within_screens=state['within_screens'], metrics=result))
    final = rows[-1]
    if record['first_excluded_set'] is not None:
        for name, row in final['metrics'].items():
            crossing = record['first_print_crossings'].get('all_'+name)
            if crossing and crossing['native_set'] == end:
                assert (crossing['element'], crossing['node']) == (row['element'], row['node'])
                assert abs(crossing['distance_to_bearing_nodes_mm']-row['tied_node_distance_mm']) < 1.e-9
    result = dict(case=case, checkpoint_sha256=digest(audit_path), mesh_sha256=spec['mesh_sha256'],
                  STEP_sha256=STEP_HASH, stations=rows, references=PLA, element_count=len(solids),
                  scope='Signed native unaveraged corner results, including same-node spread across incident tetrahedra. '
                        'Reaching a printed tensile-coupon mean is a comparison for this elastic PLA model.')
    write_json(AUDIT/f'{case}_{folder.name}_tab_corners.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    analyse(parser.parse_args().folder)

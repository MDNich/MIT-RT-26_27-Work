"""Recover through-layer stress along the same two tab-root edges on the fine and coarse fixtures."""
import argparse
from pathlib import Path

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_tab_crossing import local_points
from stage_snug_fit import AUDIT, MESH

OFFSET = 2100001
FORWARD = 'snug125_nylon_lateral_friction_locked_pin1'
ROOT_FACES = {'low_Y': (7, 44), 'high_Y': (6, 38)}


def edges(mesh):
    tetra = mesh['tets'][:, :4]
    span = {}
    for name, (wall, bearing) in ROOT_FACES.items():
        surface = np.intersect1d(mesh[str(wall)], mesh[str(bearing)])
        nodes = np.intersect1d(surface, tetra)
        nodes = nodes[np.argsort(mesh['points'][nodes, 0])]
        xyz = local_points(mesh['points'][nodes])
        assert np.min(np.diff(xyz[:, 0])) > 0 and np.ptp(xyz[:, 1:], axis=0).max() < 1e-7
        assert np.allclose(xyz[[0, -1], 0], [0., 6.36], rtol=0, atol=1e-7)
        pieces = []
        for a, b in zip(nodes[:-1], nodes[1:], strict=True):
            owner = np.flatnonzero((tetra == a).any(1) & (tetra == b).any(1))
            assert len(owner) >= 1
            ia = (tetra[owner] == a).argmax(1)
            ib = (tetra[owner] == b).argmax(1)
            pieces.append((1200001+owner, ia, ib))
        span[name] = (xyz, nodes+OFFSET, pieces)
    return span


def stress_band(x, endpoint_values, limits):
    # The native stress has four corner values per tetrahedron. Integrate its
    # linear trace separately on each incident element, keeping both envelopes.
    begin, end = limits
    integral = np.zeros(3)
    coverage = 0.
    for a, b, values in zip(x[:-1], x[1:], endpoint_values, strict=True):
        lo, hi = max(begin, a), min(end, b)
        if hi <= lo:
            continue
        fraction = (.5*(lo+hi) - a)/(b-a)
        mean = values[:, 0] + fraction*(values[:, 1]-values[:, 0])
        integral += (hi-lo)*np.array([mean.min(), mean.mean(), mean.max()])
        coverage += hi-lo
    assert abs(coverage - (end-begin)) < 1e-9
    return (integral/coverage).tolist()


def recover(raw, size, mesh_sha, states):
    path = MESH/f'case_{size}.npz'
    verified(path, mesh_sha)
    with np.load(path) as mesh:
        edge = edges(mesh)
    geometry = {}
    for name, (xyz, nodes, pieces) in edge.items():
        assert np.max(abs(raw.mesh.nodes[positions(raw.mesh.nnum, nodes)] - xyz)) < 1e-7
        geometry[name] = dict(faces=list(ROOT_FACES[name]), nodes=nodes.tolist(), ends_mm=xyz[[0,-1]].tolist(),
                              incident_elements=[ids.tolist() for ids, _, _ in pieces])
        x = xyz[:, 0]
        trial = [np.array([[2+3*a, 2+3*b]]) for a,b in zip(x[:-1],x[1:],strict=True)]
        for limits in ((x[0], x[-1]), (1.59, 4.77)):
            assert np.allclose(stress_band(x,trial,limits),2 + 1.5*sum(limits),atol=1e-10,rtol=0)
    result = []
    for native_set, travel in states:
        enum, data, labels = raw.element_solution_data(native_set-1,'ENS')
        station = {}
        for name, (xyz, nodes, pieces) in edge.items():
            trace = []
            for j, (ids, ia, ib) in enumerate(pieces):
                ix = positions(enum, ids)
                corners = np.stack([labels[i] for i in ix])
                rr = np.arange(len(ids))
                assert np.all(corners[rr, ia] == nodes[j]) and np.all(corners[rr, ib] == nodes[j+1])
                s = np.stack([data[i] for i in ix]).reshape(-1, 4, 6).astype(float)
                trace.append(np.column_stack((s[rr, ia, 2], s[rr, ib, 2])))
            x = xyz[:, 0]
            station[name] = dict(full_edge_MPa=stress_band(x, trace, (x[0], x[-1])),
                                 middle_half_MPa=stress_band(x, trace, (1.59, 4.77)))
        result.append(dict(native_set=native_set, travel_mm=travel, edges=station))
    return dict(mesh_sha256=mesh_sha, geometry=geometry, states=result,
                scope='Length-averaged signed layer stress from linear traces of unaveraged native corner stresses. '
                      'Each triple gives the lowest, mean and highest length average over incident-element choices '
                      'on each segment. The central 3.18 mm uses the same physical endpoints on both meshes.')


def checkpoint(folder):
    spec=read(folder/'capture.json')
    name=spec['case']
    assert name==FORWARD+'_m15'
    path=AUDIT/f'{name}_{folder.name}_checkpoint.json'
    audit=read(path)
    verified(folder/'pull.rst',audit['rst_sha256'])
    mesh_sha=read(AUDIT/'local_inputs_m15.json')[name]['mesh_sha256']
    stop = audit['first_excluded_set'] or audit['converged_sets']
    rows = audit['states'][stop-2:stop]
    data=recover(reader.read_binary(folder/'pull.rst'),'1.5',mesh_sha,[(r['native_set'],r['travel_mm']) for r in rows])
    data.update(checkpoint_sha256=digest(path),rst_sha256=audit['rst_sha256'])
    write_json(AUDIT/f'{name}_{folder.name}_tab_edge.json',data)


def closed(case, record, folder):
    size = '3' if case.endswith('_m3') else '1.5'
    verified(folder/'pull.rst', record['native_rst_sha256'])
    material = ROOT/'validation/pull_material'/f'{case}.json'
    verified(material, record['print_material_sha256'])
    full = read(material)['history']
    cutoffs = [r['native_set'] for r in record['first_print_reference_crossings'].values()]
    if record['first_contact_screen_exceeded']:
        cutoffs.append(record['first_contact_screen_exceeded']['native_set'])
    stop = min(cutoffs, default=full[-1]['native_set'])
    states = [(r['native_set'],r['travel_mm']) for r in full if r['loadstep']==3 and r['native_set']<=stop]
    data = recover(reader.read_binary(folder/'pull.rst'),size,record['case_mesh_sha256'],states)
    for path in sorted(AUDIT.glob(case+'_ls*_tab_edge.json')):
        earlier = read(path)
        assert earlier['checkpoint_sha256'] in {r['checkpoint_sha256'] for r in record['verified_checkpoints']}
        assert data['geometry'] == earlier['geometry']
        by_set = {r['native_set']:r for r in data['states']}
        for before in earlier['states']:
            current = by_set[before['native_set']]
            assert abs(current['travel_mm']-before['travel_mm'])<1.e-7
            assert current['edges']==before['edges']
    data.update(case=case,rst_sha256=record['native_rst_sha256'],material_sha256=record['print_material_sha256'])
    path=AUDIT/f'{case}_tab_edge_history.json'
    write_json(path,data)
    return path


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder',type=Path)
    checkpoint(p.parse_args().folder)

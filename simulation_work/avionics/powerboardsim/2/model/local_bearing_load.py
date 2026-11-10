"""Check the equivalent board-normal force location on each printed-tab screw bearing."""
import argparse
import re

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from local_equilibrium import positions


def normal_resultant(arms, forces, radius):
    axial = forces[:, 2]
    normal = float(axial.sum())
    first_moment = axial @ arms[:, :2]
    magnitude = float(np.linalg.norm(first_moment))
    # For loads of a single sign anywhere in this disk, |sum(Fz*r)| <= radius*|sum(Fz)|.
    # Permitting both signs requires at least this much load opposite the net normal force.
    opposed = max(0., (magnitude / radius - abs(normal)) / 2)
    assert opposed <= min(np.maximum(axial, 0).sum(), -np.minimum(axial, 0).sum()) + 1.e-8
    return dict(normal_force_N=normal, first_moment_XY_Nmm=first_moment.tolist(),
                equivalent_offset_XY_mm=(first_moment / normal).tolist() if abs(normal) > 1.e-7 else None,
                minimum_opposing_load_N=opposed)


def bearing_readback(rst, deck, expected_tets, radius):
    """Prepare the section and tie maps once, then evaluate a one-based saved state."""
    grid = rst.grid.cell_data
    element_order = np.argsort(rst.mesh.enum)
    def elements(etype):
        numbers = np.sort(grid['ansys_elem_num'][grid['ansys_etype'] == etype])
        indices = element_order[positions(rst.mesh.enum[element_order], numbers)]
        connectivity = [rst.mesh.elem[i][10:] for i in indices]
        return numbers, np.stack(connectivity) if connectivity else np.empty((0, 2), int)

    tets, tet_nodes = elements(850)
    beams, beam_nodes = elements(851)
    seats, seat_nodes = elements(854)
    assert len(tets) == expected_tets and tet_nodes.shape[1] == 10
    ends = beam_nodes[:, :2]
    assert np.array_equal(ends, np.arange(950001, 950009).reshape(4, 2))
    if len(seats):
        assert np.array_equal(ends, seat_nodes)
    coupled_nodes = []
    for pilot in ends[:, 0]:
        coupled = np.array([int(x) for x in re.findall(r'(?im)^CERIG,' + str(pilot) + r',(\d+),UXYZ', deck)])
        assert len(coupled) >= 3 and len(np.unique(coupled)) == len(coupled)
        coupled_nodes.append(coupled)
    all_nodes = np.concatenate(coupled_nodes)
    assert len(np.unique(all_nodes)) == len(all_nodes)
    incident = np.flatnonzero(np.isin(tet_nodes, all_nodes).any(axis=1))
    ids, inverse = np.unique(tet_nodes[incident], return_inverse=True)
    def evaluate(k):
        numbers, enf, _ = rst.element_solution_data(k-1, 'ENF')
        assembled = np.zeros((len(ids), 3))
        tet_force = np.stack([enf[j] for j in positions(numbers, tets[incident])]).reshape(-1, 3)
        np.add.at(assembled, inverse.ravel(), tet_force)
        feet = []
        for i, (pilot, _) in enumerate(ends):
            coupled = coupled_nodes[i]
            center = rst.mesh.nodes[positions(rst.mesh.nnum, [pilot])][0]
            arms = rst.mesh.nodes[positions(rst.mesh.nnum, coupled)] - center
            assert np.linalg.norm(arms[:, :2], axis=1).max() <= radius
            load = -assembled[positions(ids, coupled)]
            force = load.sum(0)
            moment = np.cross(arms, load).sum(0)
            beam = enf[positions(numbers, beams)[i]].reshape(-1, 6)[0]
            seat_force = np.zeros(3)
            if len(seats):
                block = enf[positions(numbers, seats)[i]]
                if block is not None and len(block):
                    seat_force = block.reshape(2, 3)[0]
            force_error = float(abs(force - beam[:3] - seat_force).max())
            moment_error = float(abs(moment - beam[3:]).max())
            assert force_error < .002 and moment_error < .002, (k, pilot, force_error, moment_error)
            record = normal_resultant(arms, load, radius)
            feet.append(dict(pilot=int(pilot), bearing_nodes=len(coupled), original_xy_mm=center[:2].tolist(),
                             force_XYZ_N=force.tolist(), moment_XYZ_Nmm=moment.tolist(),
                             max_abs_Z_offset_mm=float(abs(arms[:, 2]).max()), beam_end_force_error_N=force_error,
                             beam_end_moment_error_Nmm=moment_error, **record))
        return feet
    return evaluate


def check(case, campaign, stage, travel):
    radius = 3.75  # The radial node selection in local_case_geometry.py, in the board XY plane.
    folder = ROOT / '.runtime/archive' / campaign / case
    receipt = ROOT / '.runtime/receipts' / campaign / case
    ledger = read(receipt / 'archived.json')
    assert (receipt / 'released.txt').exists() and (ledger['case'], ledger['campaign']) == (case, campaign)
    hashes = {f['name']: f['sha256'] for f in ledger['files']}
    for name in ('local_job.json', 'model.inp', 'pull.rst'):
        verified(folder / name, hashes[name])
    job = read(folder / 'local_job.json')
    assert job['cased'] and job['case'] == case and job['job'] == 'pull'
    path = ROOT / 'validation' / ('pull_material' if stage == 'pull' else 'installation_material') / (case + '.json')
    material = read(path)
    assert material['case'] == case and material['campaign'] == campaign and material['rst_sha256'] == hashes['pull.rst']
    rows = [r for r in material['history'] if np.isclose(r['travel_mm'], travel, rtol=0, atol=1.e-8)]
    row, = rows
    k = row['native_set']
    assert all(k < crossing['native_set'] for name, crossing in material['first_reference_crossings'].items() if name.startswith('all_'))
    rst = reader.read_binary(folder / 'pull.rst')
    assert rst._resultheader['ls_table'][k-1, 1] != 999999 and np.isclose(rst.time_values[k-1], row['time_s'], atol=1.e-8, rtol=0)
    deck = (folder / 'model.inp').read_text()
    feet = bearing_readback(rst, deck, material['case_tets'], radius)(k)
    result = dict(case=case, campaign=campaign, stage=stage, native_set=k, travel_mm=travel, model_radius_mm=radius,
                  rst_sha256=hashes['pull.rst'], deck_sha256=hashes['model.inp'], material_scope_sha256=digest(path),
                  feet=feet, scope='Reference-configuration first moment of the board-normal loads transmitted through '
                  'the modeled rigid PLA bearing ties. The offset is computed from the full force distribution. '
                  'It tests whether single-signed axial loads alone could reproduce that resultant inside the '
                  'modeled disk. Actual bearing pressure, thread contact and screw-head slip are unresolved.')
    out = ROOT / 'validation/bearing_loads' / f'{case}_{stage}_{k}.json'
    write_json(out, result)
    print(case, [round(np.linalg.norm(f['equivalent_offset_XY_mm']), 4) for f in feet],
          [round(f['minimum_opposing_load_N'], 3) for f in feet])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('case')
    p.add_argument('stage', choices=('installation', 'pull'))
    p.add_argument('travel_mm', type=float)
    p.add_argument('--campaign', default='nov08_01')
    args = p.parse_args()
    check(args.case, args.campaign, args.stage, args.travel_mm)

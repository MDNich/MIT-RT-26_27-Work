"""Measure simultaneous changes in cell-centre spacing on the prestressed whole-board histories."""
import argparse

import numpy as np

from audit_local import ROOT, read
from basis_comparison import field_files
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from native_rst import read_rst
from seeded_motion import FS
from snug_edge_cell_travel import get_geometry
from snug_pla_vibration import full_coordinates
from stage_snug_fit import AUDIT


def installed_cells(variant, campaign, modal, folder, geometry):
    evidence = read(ROOT/'validation/cell_force'/f'{variant}.json')
    assert evidence['basis_rst_sha256'] == modal['rst_sha256']
    cache = ROOT/'.runtime/post'/campaign/modal['case']
    rst = read_rst(folder/'file.rst')
    verified(cache/'cell_mass_weights.npz', evidence['mass_weights_sha256'])
    verified(cache/'cell_mass_mean.npz', evidence['mean_shapes_sha256'])
    order = sorted(map(int, evidence['geometry']), key=lambda mat: evidence['geometry'][str(mat)]['centroid_mm'][0])
    assert order == [176, 191, 187]
    with np.load(cache/'cell_mass_weights.npz') as data:
        nodes = data['nodes']
        weights = np.stack([data['weights'][np.flatnonzero(data['materials'] == mat).item()] for mat in order])
    with np.load(cache/'cell_mass_mean.npz') as data:
        assert np.array_equal(data['frequencies_Hz'], rst.time_values)
        mean = 1000*np.stack([data['mean'][np.flatnonzero(data['materials'] == mat).item()] for mat in order])
    assert np.allclose(weights.sum(1), 1., rtol=0, atol=1e-12)
    indices = np.searchsorted(rst.mesh.nnum, nodes)
    assert np.array_equal(rst.mesh.nnum[indices], nodes)
    centres = weights @ (1000*rst.mesh.nodes[indices])
    assert np.allclose(centres[0], geometry['locked_centroid_mm'], rtol=0, atol=1e-10)
    stems = field_files(modal['case'], campaign, modal['rst_sha256'], rst.nsets) if variant != 'bare' else None
    nodal = 1000*displacement_basis(rst, nodes, stems)
    # An independent reconstruction at selected times below sums nodal fields first.
    assert np.allclose(weights @ nodal, mean.transpose(2, 0, 1), rtol=1e-11, atol=1e-8)
    return centres, mean, weights, nodal, evidence


def measure(variant, campaign, methods):
    modal, folder, freq, geometry, left_to_clamps, _, _, _, _ = get_geometry(variant, campaign)
    centres, mean, weights, nodal, evidence = installed_cells(variant, campaign, modal, folder, geometry)
    baselines = np.diff(centres, axis=0)
    pitch = np.linalg.norm(baselines, axis=1)
    directions = baselines / pitch[:, None]
    assert np.all(directions[:, 0] > .9999) and np.all((23.7 < pitch) & (pitch < 24.1))
    for method in methods:
        axes = {}
        for axis in 'XYZ':
            q, source_hash, drive_hash = full_coordinates(variant, campaign, method, axis, modal, folder, freq)
            relative_modes = mean[:-1] - mean[1:]
            along = np.einsum('pc,pcm->mp', directions, relative_modes)
            # A rigid translation cancels in each pair. A rigid rotation contributes
            # zero along the line joining its end points to first order.
            spin = np.cross([.23, -.41, .32], centres)
            assert np.max(abs(np.einsum('pc,pc->p', directions, np.diff(spin, axis=0)))) < 1e-12
            approach = q @ along
            frozen = q @ (left_to_clamps @ directions[0])
            high = freq <= 3500.
            below = q[:, high] @ along[high]
            travel = (q @ relative_modes.reshape(6, len(freq)).T).reshape(-1, 2, 3)
            distance_change = pitch - np.linalg.norm(baselines - travel, axis=2)
            assert np.allclose(approach, np.einsum('spc,pc->sp', travel, directions), rtol=0, atol=1e-10)
            events = {}
            evidence_hash = {}
            if variant != 'bare':
                onset_path = AUDIT/f'{variant}_outer_onset_{axis}_{method}.json'
                witness_path = onset_path.with_name(onset_path.stem + '_witness.json')
                onset, witness = read(onset_path), read(witness_path)
                assert onset['basis_rst_sha256'] == modal['rst_sha256'] and onset['input_sha256'] == drive_hash
                assert witness['source_sha256'] == digest(onset_path)
                for side, row in witness['cells'].items():
                    station = row['sample']
                    lower = onset['cells'][side]['last_contiguous_clear_sample']
                    assert lower < onset['cells'][side]['first_intersecting_sample'] <= station
                    assert row['first_intersection_interval_ms'] == [1000*lower/FS, 1000*station/FS]
                    events[side] = dict(sample=station, time_ms=1000*station/FS,
                                        approach_um=(1000*approach[station]).tolist(),
                                        left_relative_to_clamps_um=1000*frozen[station],
                                        middle_relative_to_left_clamps_um=1000*(frozen[station]-approach[station, 0]))
                evidence_hash = dict(interval=digest(onset_path), witness=digest(witness_path))
            peaks = {}
            observed = {event['sample'] for event in events.values()}
            for pair, label in enumerate(('left_middle', 'middle_right')):
                signal = approach[:, pair]
                positive, negative = int(signal.argmax()), int(signal.argmin())
                observed.update([positive, negative])
                peaks[label] = dict(peak_approach_um=1000*signal[positive], peak_approach_sample=positive,
                                    peak_opening_um=-1000*signal[negative], peak_opening_sample=negative,
                                    peak_approach_3500Hz_um=1000*below[:, pair].max(),
                                    peak_opening_3500Hz_um=-1000*below[:, pair].min(),
                                    max_axial_minus_distance_change_um=1000*float(abs(signal-distance_change[:, pair]).max()))
            station = peaks['left_middle']['peak_approach_sample']
            # The frame velocity transported from left to middle differs by a rotation
            # perpendicular to their separation. The axial reference is identical.
            at_peak = dict(left_relative_to_clamps_um=1000*frozen[station],
                           middle_relative_to_left_clamps_um=1000*(frozen[station]-approach[station, 0]))
            observed = np.array(sorted(observed))
            field = (q[observed] @ nodal.reshape(len(freq), -1)).reshape(len(observed), -1, 3)
            moved = weights @ field
            direct = np.einsum('spc,pc->sp', -np.diff(moved, axis=1), directions)
            error = float(np.max(abs(direct-approach[observed])))
            assert error < 1e-9
            axes[axis] = dict(pairs=peaks, at_left_middle_peak=at_peak,
                              peak_left_travel_toward_middle_relative_to_clamps_um=1000*frozen.max(),
                              verified_samples=observed.tolist(), max_nodal_reconstruction_error_um=1000*error,
                              first_outer_intersection=events, event_sources_sha256=evidence_hash,
                              coordinate_source_sha256=source_hash, input_sha256=drive_hash)
        path = AUDIT/f'{variant}_cell_spacing_{method}.json'
        write_json(path, dict(variant=variant, campaign=campaign, method=method, basis_rst_sha256=modal['rst_sha256'],
                              static_rst_sha256=geometry['static_sha256'], cell_weights_sha256=evidence['mass_weights_sha256'],
                              cell_mean_sha256=evidence['mean_shapes_sha256'], material_order=[176, 191, 187],
                              locked_centres_mm=centres.tolist(), locked_pitch_mm=pitch.tolist(), axes=axes,
                              scope='Simultaneous mass-centre approach from bolt lock over nine seconds along each installed '
                                    'line of centres. Contact is linearized. Cell-centre spacing does not measure a pocket gap.'))
        print(path.name, [round(v['pairs']['left_middle']['peak_approach_um'], 3) for v in axes.values()], flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant', choices=('bare', 'snug125_nylon', 'snug125_aluminium', 'snug125_nylon_mesh15'))
    p.add_argument('--campaign', default='nov08_01')
    p.add_argument('--methods', nargs='+', choices=('native', 'exact'), default=['native', 'exact'])
    args = p.parse_args()
    measure(args.variant, args.campaign, args.methods)

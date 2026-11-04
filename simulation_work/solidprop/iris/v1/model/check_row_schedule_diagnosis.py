"""Trace a failed heating-row event without changing either solver or its gates.

Replay conversion from immutable native temperatures, then compare the native
and independent mass ledgers immediately around their removal events. Values
from this diagnostic are not accepted motor predictions or convergence pairs.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from ops import ROOT, TMP, atomic, disks, host_check, utc
from radial_model import RadialModel, TABLE
from validate_run import validate


def diagnose(name, last_index=2100):
    run = TMP / 'runs' / name
    native_audit = validate(run, allow_paused=True)
    cfg = json.loads((run / 'config.json').read_text())
    mesh = json.loads((run / 'mesh_map.json').read_text())
    g = cfg['geometry']
    nf = g['faces_per_row']
    plane = (g['angular_divisions'] + 1) * (g['axial_divisions'] + 1)
    model = RadialModel(cfg)
    independent = model.initial()
    replay = np.zeros_like(independent.alpha)
    old_temperature = independent.T.copy()
    rv = cfg['material']['virgin_reference_density_kg_m3']
    rc = cfg['material']['char_reference_density_kg_m3']
    assert last_index <= native_audit['accepted_steps']
    assert last_index * cfg['macro_dt_s'] <= cfg['heating']['pulse_duration_s']
    event_indices = []
    for index in range(1, last_index + 1):
        audit = json.loads((run / 'checkpoints' / f'audit_{index:06d}.json').read_text())
        if audit['elements_scheduled_for_removal']:
            event_indices.append(index)
    sampled = {i for event in event_indices for i in range(max(1, event - 4), min(last_index, event + 2) + 1)}
    records = []
    archive_hash = hashlib.sha256()
    replay_error = 0.0
    for index in range(1, last_index + 1):
        if index % 200 == 0:
            host_check()
        path = run / 'checkpoints' / f'state_{index:06d}.json.gz'
        archive_hash.update(path.read_bytes())
        with gzip.open(path, 'rt') as stream:
            native = json.load(stream)
        audit = json.loads((run / 'checkpoints' / f'audit_{index:06d}.json').read_text())
        dt = audit['dt_s']
        assert abs(dt - cfg['macro_dt_s']) < 1e-10 and audit['native_substep'] == 1
        independent = model.step(independent, dt)
        assert independent is not None
        assert abs(independent.time - native['time_s']) < 1e-8
        temperature = np.array([
            np.mean([native['temperatures'][str(1 + j * plane + k)] for k in range(plane)])
            for j in range(len(model.r))])
        native_alpha = np.array([
            np.mean([native['alpha'][str(1 + j * nf + k)] for k in range(nf)])
            for j in range(model.np)])
        first = audit['rows_removed']
        midpoint = .5 * (temperature + old_temperature)
        gp = midpoint[:-1, None] * model.N[None, :, 0] + midpoint[1:, None] * model.N[None, :, 1]
        rate = 333 * np.exp(-64081 / (8.31446261815324 * (gp[:model.np] + 273.15)))
        replay[first:] = 1 - (1 - replay[first:]) * np.exp(-rate[first:] * dt)
        replay_error = max(replay_error, float(np.max(abs(replay[first:].mean(axis=1) - native_alpha[first:]))))
        if index in sampled:
            # Sample the row actually solved by ANSYS, not stale fields from
            # a previously killed row. Each ledger keeps its own mass basis.
            j = first
            ids = [str(1 + j * nf + k) for k in range(nf)]
            volume = sum(mesh['elements'][eid]['volume'] for eid in ids)
            consumed = sum(native['char_consumed'].get(eid, 0) for eid in ids)
            weighted_alpha = float(np.sum(independent.alpha[j] * model.w[j]) / model.vol[j])
            native_residual = (rv - (rv - rc) * native_alpha[j]) * volume - consumed
            independent_residual = (rv - (rv - rc) * weighted_alpha) * model.vol[j] - independent.consumed[j]
            endpoint_gp = temperature[j] * model.N[:, 0] + temperature[j + 1] * model.N[:, 1]
            kv = np.interp(endpoint_gp, TABLE[:, 0], TABLE[:, 1])
            kc = np.interp(endpoint_gp, TABLE[:, 0], TABLE[:, 2])
            reconstructed_flux = float(np.mean(-((1 - replay[j]) * kv + replay[j] * kc)
                                               * (temperature[j + 1] - temperature[j]) / model.dr[j]))
            native_flux = float(np.mean([native['radial_flux'][eid] for eid in ids]))
            common = max(native['layer'], independent.layer)
            records.append(dict(index=index, time_s=native['time_s'], row_index=j,
                native_layer=native['layer'], independent_layer=independent.layer,
                native_alpha=float(native_alpha[j]), independent_mean_alpha=float(independent.alpha[j].mean()),
                independent_weighted_alpha=weighted_alpha,
                replayed_native_mean_alpha=float(replay[j].mean()),
                replayed_native_weighted_alpha=float(np.sum(replay[j] * model.w[j]) / model.vol[j]),
                native_residual_fraction=float(native_residual / (rv * volume)),
                independent_residual_fraction=float(independent_residual / (rv * model.vol[j])),
                native_consumed_fraction=float(consumed / (rv * volume)),
                independent_consumed_fraction=float(independent.consumed[j] / (rv * model.vol[j])),
                native_row_flux_W_m2=native_flux, reconstructed_native_flux_W_m2=reconstructed_flux,
                native_flux_replay_difference_W_m2=native_flux-reconstructed_flux,
                max_temperature_difference_K=float(np.max(abs(temperature[common:]-independent.T[common:])))))
        old_temperature = temperature
    result = dict(created_utc=utc(), runtime=name, native_audit=native_audit,
        last_replayed_index=last_index, native_prefix_sha256=archive_hash.hexdigest(),
        config_sha256=hashlib.sha256((run/'config.json').read_bytes()).hexdigest(),
        model_sha256=hashlib.sha256((ROOT/'model/radial_model.py').read_bytes()).hexdigest(),
        diagnostic_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        max_native_conversion_replay_error=replay_error, removal_cutoff_fraction=cfg['numerics']['row_residual_mass_fraction'],
        records=records,
        qualification='Diagnostic only. Native element-average ledgers and independent quadrature-weighted ledgers remain distinct. Replayed conversion uses radially averaged native temperatures and the unchanged intended reaction law. This neither calibrates the law nor accepts the failed spatial convergence pair.')
    atomic(ROOT/'validation'/f'row_schedule_diagnosis_{name}.json', result)
    print(name, 'conversion replay maximum error:', replay_error)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('runtime')
    parser.add_argument('--last-index', type=int, default=2100)
    args = parser.parse_args()
    disks()
    diagnose(args.runtime, args.last_index)

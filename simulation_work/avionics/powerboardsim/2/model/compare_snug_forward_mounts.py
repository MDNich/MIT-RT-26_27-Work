"""Compare matching native cell travels, mounting loads and pressures through the second aluminium checkpoint."""
import numpy as np

from audit_local import read
from compare_pull import series
from compare_snug_forward_checkpoint import CHECKPOINTS as EARLY_CHECKPOINTS, OUTPUT as EARLY_OUTPUT
from film_identity import digest, verified, write_json
from installation_material import PLA
from snug_directional_result import first_bracket
from stage_snug_fit import AUDIT

CHECKPOINTS = {key: name.replace('ls3_ss7', 'ls3_ss12') for key, name in EARLY_CHECKPOINTS.items()}
OUTPUT = AUDIT/'forward_mount_checkpoint_comparison.json'


def compare():
    early = read(EARLY_OUTPUT)
    records = {}
    mounts = {}
    pressures = {}
    source_hashes = {}
    for key, name in CHECKPOINTS.items():
        previous = AUDIT/EARLY_CHECKPOINTS[key]
        verified(previous, early['checkpoint_sha256'][key])
        old = read(previous)
        rec = read(AUDIT/name)
        assert rec['states'][:old['converged_sets']] == old['states']
        assert rec['input_sha256'] == early['input_sha256'][key]
        assert rec['converged_sets'] == 21 and not rec['completed']
        assert rec['first_excluded_set'] is None and not rec['first_print_crossings']
        mount_path = AUDIT/name.replace('_checkpoint.json', '_mount_reactions.json')
        mount = read(mount_path)
        assert mount['checkpoint_sha256'] == digest(AUDIT/name) and mount['rst_sha256'] == rec['rst_sha256']
        assert len(mount['states']) == 21
        pressure_path = AUDIT/name.replace('_checkpoint.json', '_cell_pressure.json')
        if key == 'nylon':
            pressure_path = pressure_path.with_name(pressure_path.name.replace('ls3_ss12', 'ls3_ss18'))
        pressure = read(pressure_path)
        pressure_cp = pressure_path.with_name(pressure_path.name.replace('_cell_pressure.json', '_checkpoint.json'))
        verified(pressure_cp, pressure['checkpoint_sha256'])
        pressure_source = read(pressure_cp)
        assert pressure_source['rst_sha256'] == pressure['rst_sha256']
        assert pressure_source['states'][:21] == rec['states']
        records[key], mounts[key] = rec, mount
        pressures[key] = {r['native_set']: r for r in pressure['states']}
        source_hashes[key] = dict(checkpoint=digest(AUDIT/name), mount=digest(mount_path),
                                  pressure=digest(pressure_path), pressure_checkpoint=digest(pressure_cp))
    bare, baseline = series(early['bare_case'])
    assert bare['rst_sha256'] == early['bare_rst_sha256']
    common = []
    for nylon, aluminium in zip(records['nylon']['states'], records['aluminium']['states'], strict=True):
        assert nylon['native_set'] == aluminium['native_set'] and nylon['loadstep'] == aluminium['loadstep']
        assert abs(nylon['travel_mm']-aluminium['travel_mm']) < 1e-10
        if nylon['loadstep'] != 3:
            continue
        travel = nylon['travel_mm']
        common.append(dict(travel_mm=travel, nylon=nylon, aluminium=aluminium,
                           bare=first_bracket(baseline, 'ux_mm', travel, 1),
                           aluminium_to_nylon_force_ratio=aluminium['cell_force_N']/nylon['cell_force_N']))
    assert len(common) == 12 and common[:7] == early['common_native_travel']
    summaries = {}
    for key, rec in records.items():
        final = rec['states'][-1]
        tab = mounts[key]['states'][-1]
        assert tab['native_set'] == final['native_set'] == 21
        best = max(tab['tabs'], key=lambda row: row['peak_shank_fibre_MPa'])
        pressure = pressures[key][21]
        assert pressure['travel_mm'] == final['travel_mm'] and pressure['actuator_N'] == final['cell_force_N']
        summaries[key] = dict(
            PLA_peak_MPa={p: final['printed_coupon_percent'][p]*PLA[p]/100
                          for p in ('in_plane_tension_MPa', 'layer_tension_MPa')},
            PLA_coupon_percent=final['printed_coupon_percent'], peak_screw=best,
            tab_X_travel_range_mm=[min(t['translation_XYZ_mm'][0] for t in tab['tabs']),
                                   max(t['translation_XYZ_mm'][0] for t in tab['tabs'])],
            minimum_opposing_bearing_load_range_N=[min(t['minimum_opposing_load_N'] for t in tab['tabs']),
                                                  max(t['minimum_opposing_load_N'] for t in tab['tabs'])],
            cells=pressure['cells'])
        assert all(np.isclose(a['travel_mm'], b['travel_mm'], rtol=0, atol=1e-10)
                   for a, b in zip(rec['states'], records['nylon']['states'], strict=True))
    result = dict(early, checkpoint_sha256={k: v['checkpoint'] for k, v in source_hashes.items()},
                  earlier_comparison_sha256=digest(EARLY_OUTPUT), common_native_travel=common,
                  supporting_audit_hashes=source_hashes, final_station_material_and_mounts=summaries,
                  scope='Native local-fixture comparison at twelve exact common imposed cell travels. '
                        'Mount forces, screw stress decomposition and native pressure quadrature are independently checked. '
                        'Peak pressures and local stresses are not spatially converged; no sleeve, thread or assembly strength limit is established.')
    write_json(OUTPUT, result)
    print('Verified twelve common stations; final forces:', [common[-1][k]['cell_force_N'] for k in records])


if __name__ == '__main__':
    compare()

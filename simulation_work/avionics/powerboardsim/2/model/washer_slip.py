"""Recover the October washer contact measures and check each locked platen against its pilot."""
import argparse
import shutil
from pathlib import Path

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read, table
from compare_pull_laws import loading_curve
from film_identity import digest, verified, write_json


OUT = ROOT / 'validation/washer_slip'
COUNTS = ('open_far', 'open_near', 'sliding', 'sticking')
FIELDS = ('max_pressure_MPa', 'max_friction_MPa', 'max_slide_mm')
LOCAL_REFERENCE = ROOT / '.runtime/washer_slip_control/contact_history_v2.csv'
CONTROL = {'contact_history_v2.csv': 'f299b72f45dee585171e2e5547d442b43c8229e125aff425c8b4332e70119484',
           'contact_v2.dat': 'd6425a2f7d69bf2e5cba4d4706c277994c61052d1491e80e90428cf037fb8ef5'}


def recover(raw, cfg, scope, inventory):
    g = raw.grid.cell_data
    clamp = g['ansys_etype'] == 3
    ids = g['ansys_elem_num'][clamp]
    pairs = g['ansys_real_constant'][clamp]
    assert np.array_equal(np.unique(pairs, return_counts=True), [[1, 2, 3, 4], [768]*4])
    sets = np.flatnonzero(raw._resultheader['ls_table'][:, 1] != 999999) + 1
    assert np.array_equal(inventory['set'], sets)
    assert np.allclose(raw.time_values[sets-1], inventory['time'], atol=1e-8, rtol=0)
    rows = []
    for num, state in zip(sets, inventory, strict=True):
        k = int(num-1)
        e, ect, nodes = raw.element_solution_data(k, 'ECT')
        m, misc, _ = raw.element_solution_data(k, 'EMN')
        ei, mi = np.searchsorted(e, ids), np.searchsorted(m, ids)
        assert np.array_equal(e[ei], ids) and np.array_equal(m[mi], ids)
        saved = np.array([ect[i] is not None for i in ei])
        assert np.array_equal(saved, [misc[i] is not None for i in mi])
        fields = np.stack([ect[i] for i in ei[saved]])
        assert fields.shape[1] == 41 and np.isin(fields[:, -1], [10, 32]).all()
        assert all(len(nodes[i]) == 4 for i in ei[saved])
        corners = fields[:, :40].reshape(-1, 4, 10)
        nmisc = np.stack([misc[i] for i in mi[saved]])
        status = corners[:, :, 0]
        assert np.isin(status, [0, 1, 2, 3]).all() and np.array_equal(status, nmisc[:, :4])
        assert np.array_equal(status.max(axis=1), nmisc[:, 40])
        counts = np.bincount(nmisc[:, 40].astype(int), minlength=4)
        counts[0] += np.count_nonzero(~saved)
        # POST1's CONT columns use an element average before taking the maximum.
        peak = corners.mean(axis=1, dtype=float)[:, [2, 3, 5]].max(axis=0)
        assert np.isfinite(peak).all()
        row = dict(native_set=int(num), loadstep=int(raw._resultheader['ls_table'][k, 0]),
                   substep=int(raw._resultheader['ls_table'][k, 1]), time=float(state['time']),
                   travel_mm=float(state['ux_mm']), **dict(zip(COUNTS, counts.tolist(), strict=True)),
                   **dict(zip(FIELDS, peak.tolist(), strict=True)),
                   sliding_corner_records=int(np.count_nonzero(status == 2)))
        if row['time'] >= cfg['pull_start_time']-1e-9:
            reactions, numbers, dofs = raw.nodal_reaction_forces(k)
            pair_force = np.array([nmisc[pairs[saved] == j, 42:45].sum(axis=0, dtype=float) for j in range(1, 5)])
            pilot_force = np.array([[reactions[(numbers == pilot) & (dofs == axis)].sum() for axis in (1, 2, 3)]
                                    for pilot in cfg['target_pilots']])
            # Each original rigid platen has only this contact and its locked pilot.
            row['max_pilot_balance_N'] = float(abs(pair_force + pilot_force).max())
            assert row['max_pilot_balance_N'] < 0.001, row
            row['clamp_support_x_N'] = pilot_force[:, 0].tolist()
        rows.append(row)
    inside = [row for row in rows if 'max_pilot_balance_N' in row and row['native_set'] <= scope]
    assert inside and inside[-1]['native_set'] == scope
    half = None
    if inside[-1]['travel_mm'] >= .5:
        half, = [row for row in inside if abs(row['travel_mm']-.5) < 1e-8]
    first = next((i for i, r in enumerate(inside) if r['sliding_corner_records']), None)
    return rows, dict(converged_sets=len(rows), locked_sets_within_screens=len(inside),
                      first_local_slip_travel_bracket_mm=None if first is None else
                      [inside[max(0, first-1)]['travel_mm'], inside[first]['travel_mm']],
                      maximum_sliding_face_count_within_screens=max(r['sliding'] for r in inside),
                      max_pilot_contact_force_error_N=max(r['max_pilot_balance_N'] for r in rows if 'max_pilot_balance_N' in r),
                      at_half_mm=half, last_within_screens=inside[-1])


def october(folder):
    proof = read(ROOT / 'validation/october_damage_reference.json')
    hashes = dict(proof['source_hashes'], **CONTROL)
    for name, value in hashes.items():
        verified(folder / name, value)
    cfg_path = ROOT / '.runtime/local_inputs/damage_cont_nominal/config.json'
    verified(cfg_path, read(ROOT / 'validation/local_inputs.json')['damage_cont_nominal']['files']['config.json'])
    rows, audit = recover(reader.read_binary(folder/'tear.rst'), read(cfg_path), proof['converged_native_sets'],
                          table(folder/'set_inventory.csv'))
    history = folder/'contact_history_v2.csv'
    native = table(history)
    assert np.array_equal(native['set'], [r['native_set'] for r in rows])
    for field in ('loadstep', 'substep', *COUNTS):
        assert np.array_equal(native[field], [r[field] for r in rows])
    assert np.allclose(native['time'], [r['time'] for r in rows], rtol=0, atol=1e-8)
    errors = {}
    for field in FIELDS:
        values = np.array([r[field] for r in rows])
        assert np.allclose(native[field], values, rtol=2e-7, atol=1e-10), field
        errors[field] = float(abs(native[field]-values).max())
    LOCAL_REFERENCE.parent.mkdir(parents=True, exist_ok=True)
    if not LOCAL_REFERENCE.exists():
        shutil.copyfile(history, LOCAL_REFERENCE)
    verified(LOCAL_REFERENCE, CONTROL['contact_history_v2.csv'])
    write_json(OUT/'october.json', dict(source_hashes=hashes, max_POST1_discrepancy=errors, **audit))


def fresh(branch):
    valid, source = loading_curve(branch, True)
    folder = ROOT / '.runtime/archive' / source['campaign'] / source['case']
    config = read(ROOT / '.runtime/local_inputs/damage_cont_nominal/config.json')
    control = read(OUT/'october.json')
    assert control['source_hashes']['contact_v2.dat'] == CONTROL['contact_v2.dat']
    rows, audit = recover(reader.read_binary(folder/'tear.rst'), config, int(valid['native_set'][-1]),
                          table(folder/'set_inventory.csv'))
    if branch == 'bare':
        # Independently repeat the complete historical contact readback on the new solve.
        verified(LOCAL_REFERENCE, CONTROL['contact_history_v2.csv'])
        native = table(LOCAL_REFERENCE)
        assert np.array_equal(native['set'], [r['native_set'] for r in rows])
        for field in ('loadstep', 'substep', *COUNTS):
            assert np.array_equal(native[field], [r[field] for r in rows])
        for field in ('time', *FIELDS):
            assert np.allclose(native[field], [r[field] for r in rows], rtol=2e-7, atol=1e-10), field
    write_json(OUT/(branch+'.json'), dict(source=source, october_control_sha256=digest(OUT/'october.json'), **audit))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('branch', choices=['october', 'bare', 'stand3_nylon', 'stand3_aluminium'])
    parser.add_argument('--archive', type=Path, help='Original October cont_nominal directory for the native control')
    args = parser.parse_args()
    if args.branch == 'october':
        if args.archive is None:
            parser.error('The October control needs --archive')
        october(args.archive)
    else:
        fresh(args.branch)

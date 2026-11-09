"""Bracket the first reported nickel damage using only converged, cross-checked fixture states."""
import numpy as np


def summarize(inventory, states):
    sets = np.array([s['native_set'] for s in states])
    if not np.array_equal(inventory['set'], sets) or np.any(np.diff(sets) <= 0):
        raise ValueError('Damage history does not cover each converged set in order')
    for field, key in [('time', 'time'), ('ux_mm', 'ux_mm'), ('fx_N', 'cell_fx_N')]:
        if not np.allclose(inventory[field], [s[key] for s in states], rtol=1e-7, atol=1e-6):
            raise ValueError(f'Damage inventory disagrees with the native fixture history for {field}')
    signal = inventory['damage']
    if (not np.isfinite(signal).all() or np.any(signal < -1e-8) or
            np.any(signal > 1.000001) or np.any(np.diff(signal) < -1e-4)):
        raise ValueError('Inconsistent section damage history')
    threshold = 1e-4
    crossed = np.flatnonzero(signal > threshold)
    def point(i):
        s = states[i]
        p = dict(native_set=s['native_set'], time=s['time'], cell_ux_mm=s['ux_mm'],
                 cell_fx_N=s['cell_fx_N'], damage=float(signal[i]))
        if 'screw1_u_mm_z' in s:
            p['top_travel_mm'] = s['screw1_u_mm_z']
        return p
    bracket = None
    if len(crossed):
        k = int(crossed[0])
        bracket = [point(k - 1) if k else None, point(k)]
    return dict(peak_damage=float(signal.max()), damage_reporting_threshold=threshold,
                max_equivalent_plastic_strain=float(inventory['peeq'].max()), damage_onset_bracket=bracket,
                nickel_material_scope_exceeded=bool(inventory['peeq'].max() > 1.55))

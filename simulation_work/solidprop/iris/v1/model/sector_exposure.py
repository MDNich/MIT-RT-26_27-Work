"""Advance the moving FE wall and record the first loss of material scope and geometry."""
import json
import os
from dataclasses import asdict
from pathlib import Path

import numpy as np

from aluminium_phase_enthalpy import MELT_K
from sector_wall import FEState, Sector


def write_json(path, data):
    path = Path(path)
    tmp = path.with_suffix('.new')
    tmp.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False), encoding='ascii')
    os.replace(tmp, path)


def pack(state):
    return {key: value.tolist() if isinstance(value, np.ndarray) else value
            for key, value in asdict(state).items()}


def unpack(data):
    return FEState(**{key: np.asarray(value) if isinstance(value, list) else value
                      for key, value in data.items()})


def observe(wall, state):
    index = max(0, len(state.virgin)-1)
    case = state.temperature[index:]
    status = {'baseline_property_limit': case[0] >= wall.cfg['case_property_limit_C']}
    if wall.cf:
        status['backing_1000_C'] = max(case) >= 1000.
    else:
        status['first_fusion'] = max(case) >= MELT_K-273.15-.25
        status['all_liquid'] = min(case) >= MELT_K-273.15+.25
    status['exhaustion'] = not len(state.virgin)
    return status, dict(time_s=state.time, remaining_mm=(wall.interface-state.nodes[0])*1000,
                        hot_C=float(state.temperature[0]), interface_C=float(case[0]), outer_C=float(case[-1]))


def integrate(settings, backend, guard, checkpoint=None, initial_record=None, interrupt=None):
    """Report an event only at exact geometric exhaustion; abort on a failed step audit.

    A restored record must be supplied by a caller which verifies its file and
    case identity. Checkpoints contain post-reaction fields and cumulative ledgers.
    """
    wall = Sector(settings['configuration'], settings['n'], settings['nc'])
    if initial_record is None:
        state = wall.initial()
        stats = dict(steps=0, cutbacks=0, sums={}, events={}, samples=[], max_step_energy_error=0.)
    else:
        state, stats = unpack(initial_record['state']), initial_record['stats']
    end = settings['horizon_s']
    dt = settings['dt_s']
    while len(state.virgin) and state.time < end-1e-11:
        guard()
        before = state.time
        # Hit the output stations so histories compare at the same physical time.
        next_output = (int(np.floor((before+1e-10)*2))+1)*.5
        state, ledger, diag = wall.advance(state, min(dt, end-before, next_output-before), backend)
        if not state.time > before:
            raise ArithmeticError('No positive advance')
        stats['steps'] += 1
        stats['cutbacks'] += diag['cutbacks']
        for key, value in ledger.items():
            stats['sums'][key] = stats['sums'].get(key, 0.) + float(value)
        stats['max_step_energy_error'] = max(stats['max_step_energy_error'], abs(diag['energy_error']))
        status, sample = observe(wall, state)
        for name, reached in status.items():
            if reached:
                stats['events'].setdefault(name, [before, state.time])
        if abs(state.time-next_output) < 1e-10 or state.time >= end-1e-11 or status['exhaustion']:
            stats['samples'].append(sample)
            if checkpoint: checkpoint(dict(state=pack(state), stats=stats))
        if interrupt and interrupt(state): break
    return dict(state=pack(state), stats=stats)


def balances(settings, record):
    model = Sector(settings['configuration'],settings['n'],settings['nc'])
    state = unpack(record['state'])
    m0, b0, h0 = model.inventory(model.initial())
    m1, b1, h1 = model.inventory(state)
    s = record['stats']['sums']
    heat = (h1-h0-s['film']-s['radiation']+s['outer']+s['face_cost']+s['face_products_h']
            +s['bulk_cost']+s['bulk_gas_h']+s['back_gas_h']-s['back_release'])
    return dict(liner_mass_relative=(m1-m0+s['bulk_gas']+s['char_products']+s['front_gas'])/m0,
                case_mass_relative=(b1-b0+s['back_gas'])/b0,
                energy_relative=heat/max(abs(s['film'])+abs(s['radiation']), 1.))

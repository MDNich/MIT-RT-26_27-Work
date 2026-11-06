"""Independent material-point and open, moving-inventory verification."""
import hashlib
import json
import math

import numpy as np
from scipy.integrate import quad, solve_ivp

from moving_surface_remap import remap
from moving_surface_thermochemistry import (Chemistry, REFERENCE_C, TEMPERATURE,
                                          bulk_step, recover_temperature, sensible)
from ops import ROOT, atomic, disks, utc
from radial_model import R, TABLE


def reference_h(t, column):
    # Direct quadrature of cp, independent of the production primitive/inverse.
    return quad(lambda x: np.interp(x, TABLE[:, 0], TABLE[:, column]), REFERENCE_C, t,
                points=[x for x in TABLE[:, 0] if min(t, REFERENCE_C) < x < max(t, REFERENCE_C)])[0]


def inverse_check():
    grid = np.r_[TEMPERATURE, [11., 27., 513., 1065., 1648., 2400.]]
    expected = np.array([[reference_h(t, 3), reference_h(t, 4)] for t in grid])
    error = float(np.max(abs(expected - sensible(grid))))
    greatest = 0.
    for v, c in [(1., 0.), (0., .46), (.31, .2)]:
        h = v * sensible(grid)[:, 0] + c * sensible(grid)[:, 1]
        greatest = max(greatest, float(np.max(abs(recover_temperature(v, c, h) - grid))))
    assert error < 3e-8 and greatest < 1e-10
    for v, c, h in [(0., 0., 0.), (1., -1., 0.), (1., 0., 1e9), (1., 0., -1e9)]:
        try:
            recover_temperature(v, c, h)
        except ValueError:
            continue
        raise AssertionError('Invalid inversion accepted')
    return dict(max_quadrature_difference_J_kg=error, max_round_trip_K=greatest)


def known_limits(law):
    virgin, char, t, dt = .75, .12, 800., .17
    reacted = virgin * (1. - math.exp(-333. * math.exp(-64081. / (R * (t + 273.15))) * dt))
    gas = (1. - law.char_yield) * reacted
    energy = reacted * (law.pyrolysis_J_per_kg_virgin + law.char_yield * reference_h(t, 4)
                        - reference_h(t, 3)) + gas * law.gas_cp_J_kg_K * (t - REFERENCE_C)
    s = bulk_step(virgin, char, t, dt, energy, law)
    assert abs(s.virgin_kg - (virgin - reacted)) < 1e-13 and abs(s.gas_out_kg - gas) < 1e-13
    assert abs(s.temperature_C - t) < 1e-10
    heat = char * (reference_h(1350., 4) - reference_h(120., 4))
    pure = bulk_step(0., char, 120., 1., heat, law)
    assert abs(pure.temperature_C - 1350.) < 1e-10 and pure.gas_out_kg == pure.reaction_J == 0
    return dict(isothermal_reacted_kg=reacted, isothermal_error_K=s.temperature_C-t,
                pure_char_heating_error_K=pure.temperature_C-1350.)


def time_check(law):
    initial = [.6, .07, 790.]
    power, duration = 50000., 4.
    def ode(time, state):
        v, c, t = state
        rate = v * 333. * math.exp(-64081. / (R * (t + 273.15)))
        effective = (law.pyrolysis_J_per_kg_virgin
                     + (1. - law.char_yield) * law.gas_cp_J_kg_K * (t - REFERENCE_C)
                     + law.char_yield * reference_h(t, 4) - reference_h(t, 3))
        capacity = v * np.interp(t, TABLE[:, 0], TABLE[:, 3]) + c * np.interp(t, TABLE[:, 0], TABLE[:, 4])
        return [-rate, law.char_yield * rate, (power - effective * rate) / capacity]
    oracle = solve_ivp(ode, (0., duration), initial, method='DOP853', rtol=1e-12, atol=1e-13)
    assert oracle.success
    errors = []
    for n in (8, 16, 32, 64):
        v, c, t = initial
        for _ in range(n):
            s = bulk_step(v, c, t, duration/n, power*duration/n, law)
            v, c, t = s.virgin_kg, s.char_kg, s.temperature_C
        errors.append(dict(steps=n, temperature_error_K=abs(t-oracle.y[2, -1]),
                           virgin_mass_error_kg=abs(v-oracle.y[0, -1])))
    for field in ('temperature_error_K', 'virgin_mass_error_kg'):
        assert all(a[field] / b[field] > 3.6 for a, b in zip(errors, errors[1:]))
    return dict(reference_final_C=oracle.y[2, -1], refinement=errors)


def moving_inventory(law):
    # Prescribe moving edges to exercise the balance over a complete recession.
    # Cell-wise reaction and supplied heat precede each geometry remap. Swept
    # virgin/char leave as solids at their stored enthalpy in this fixture.
    edges = np.array([.04, .0404, .042, .045])
    volumes = np.diff(edges**2) / 2.
    virgin = np.array([35., 490., 1150.]) * volumes
    char = (1250. * volumes - virgin) * law.char_yield
    t = np.array([1300., 825., 430.])
    h = np.sum(np.column_stack((virgin, char)) * sensible(t), axis=1)
    initial_mass, initial_H = sum(virgin+char), sum(h)
    supplied = reaction = gas_h = gas_m = swept_h = swept_m = 0.
    max_m = max_e = 0.
    for front in (.0403, .0412, .0445, .045):
        heat = volumes * 1.1e8
        updated = [bulk_step(v, c, temp, .125, q, law) for v, c, temp, q in zip(virgin, char, t, heat)]
        supplied += sum(heat)
        reaction += sum(s.reaction_J for s in updated)
        gas_h += sum(s.gas_sensible_out_J for s in updated)
        gas_m += sum(s.gas_out_kg for s in updated)
        new_edges = np.array([.045]) if front == .045 else np.linspace(front, .045, 4)
        fields = np.array([(s.virgin_kg, s.char_kg, s.solid_sensible_J) for s in updated]).T
        transfer = remap(edges, fields / volumes, new_edges)
        swept_m += sum(transfer.removed_integrals[:2])
        swept_h += transfer.removed_integrals[2]
        virgin, char, h = transfer.cell_integrals
        t = recover_temperature(virgin, char, h)
        mass_error = abs(initial_mass - sum(virgin+char) - swept_m - gas_m) / initial_mass
        energy_error = abs(initial_H + supplied - sum(h) - reaction - gas_h - swept_h) / (initial_H + supplied)
        max_m, max_e = max(max_m, mass_error), max(max_e, energy_error)
        edges, volumes = new_edges, np.diff(new_edges**2) / 2.
    assert len(h) == 0 and max_m < 1e-13 and max_e < 1e-12
    return dict(max_mass_relative_error=max_m, max_energy_relative_error=max_e,
                applied_J=supplied, initial_sensible_J=initial_H, exported_solid_sensible_J=swept_h,
                pyrolysis_J=reaction, exported_gas_sensible_J=gas_h, final_retained_J=sum(h))


def main():
    disks()
    cfg = json.loads((ROOT/'configs/continuous_heating_campaign.json').read_text())['cases'][0]['configuration']
    law = Chemistry.from_config(cfg)
    paths = ['model/moving_surface_thermochemistry.py', 'model/check_moving_surface_thermochemistry.py',
             'model/moving_surface_remap.py', 'model/radial_model.py', 'configs/continuous_heating_campaign.json']
    results = dict(checked_utc=utc(), passed=True, sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                   for p in paths}, enthalpy=inverse_check(), analytic=known_limits(law),
                   transient=time_check(law), moving_inventory=moving_inventory(law),
                   scope='Candidate bulk reaction, enthalpy and conservative remap with prescribed motion. '
                         'Surface kinetics, conduction and motor burnthrough require separate coupled verification.')
    atomic(ROOT/'validation/moving_surface_thermochemistry_verification.json', results)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()

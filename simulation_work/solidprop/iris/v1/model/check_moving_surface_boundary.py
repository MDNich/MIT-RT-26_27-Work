"""Manufactured hot-face mass, energy, cylindrical conduction and blowing checks."""
import copy
import hashlib
import json
import math

import numpy as np
from scipy.integrate import quad

from moving_surface_boundary import solve_face
from moving_surface_remap import advance_front, remap
from ops import ROOT, atomic, disks, utc
from radial_model import R, TABLE


def check(cfg, virgin, char, cell_t, face_t, outgas, radius=.045, cell_radius=.04512):
    # Work backwards from a prescribed face temperature. Integrals use quadrature
    # of the source tables. Rebuild kinetic and film fluxes independently.
    cfg = copy.deepcopy(cfg)
    law, h = cfg['char_law'], cfg['heating']
    y = cfg['material']['char_reference_density_kg_m3']/cfg['material']['virgin_reference_density_kg_m3']
    cp = h['gas_cp_J_kg_K']
    def integral(a, b, col):
        return quad(lambda x: np.interp(x, TABLE[:, 0], TABLE[:, col]), a, b,
                    points=[x for x in TABLE[:, 0] if min(a,b) < x < max(a,b)])[0]
    alpha = char / (y*virgin + char)
    partial = law['reactive_activity'] * law['pressure_Pa'] / law['pressure_reference_Pa']
    kinetic = (law['reference_rate_kg_m2_s'] * math.exp(-law['activation_energy_J_mol']/R
               * (1./(face_t+273.15) - 1./law['reference_temperature_K'])) * partial**law['pressure_exponent'])
    transport = law['mass_transfer_cap_kg_m2_s'] * partial
    char_flux = alpha * kinetic * transport / (kinetic + transport)
    speed = char_flux / (y*virgin + char)
    gas = speed * (1.-y)*virgin
    B = (gas+char_flux+outgas)*cp/h['h0_W_m2_K']
    film = h['h0_W_m2_K'] * (B / math.expm1(B) if B else 1.)
    q = ((1.-alpha)*integral(cell_t,face_t,1) + alpha*integral(cell_t,face_t,2)) / (radius*math.log(cell_radius/radius))
    exported = char_flux*integral(22.,face_t,4) + gas*cp*(face_t-22.)
    swept = speed*(virgin*integral(22.,cell_t,3) + char*integral(22.,cell_t,4))
    reaction = speed*virgin*cfg['material']['pyrolysis_enthalpy_J_kg'] + char_flux*law['effective_endothermic_cost_J_kg']
    rad = h['hot_effective_emissivity']*5.670374419e-8*((h['radiative_temperature_C']+273.15)**4-(face_t+273.15)**4)
    h['gas_temperature_C'] = face_t + (q + reaction + exported - swept - rad)/film
    face = solve_face(cell_t, virgin, char, radius, cell_radius, outgas, cfg)
    assert abs(face.temperature_C - face_t) < 1e-8
    assert abs(face.speed_m_s-speed) < 1e-13 and abs(face.h_W_m2_K-film) < 1e-7
    assert abs(face.conduction_into_solid_W_m2-q) < 1e-5
    assert abs(face.energy_residual_W_m2) < 1e-5
    assert abs((virgin+char)*face.speed_m_s-face.char_products_kg_m2_s-face.surface_pyrolysis_gas_kg_m2_s) < 1e-12
    return face, swept


def main():
    disks()
    cfg = json.loads((ROOT/'configs/continuous_heating_campaign.json').read_text())['cases'][0]['configuration']
    virgin, _ = check(cfg, 1250., 0., 400., 470., 0.)
    assert virgin.speed_m_s == 0 and virgin.char_products_kg_m2_s == 0
    quiet, _ = check(cfg, 1250., 0., 22., 22., 0.)
    assert max(abs(quiet.conduction_into_solid_W_m2), abs(quiet.convection_W_m2)) < 1e-8
    pure, _ = check(cfg, 0., 600., 1150., 1150., 0.)
    assert pure.surface_pyrolysis_gas_kg_m2_s == pure.pyrolysis_W_m2 == 0
    assert abs(pure.convection_W_m2-pure.char_removal_W_m2) < 1e-6
    radiant = copy.deepcopy(cfg)
    radiant['heating']['hot_effective_emissivity'] = .2
    mixed, swept = check(radiant, 400., 408., 750., 925., .035)
    assert mixed.h_W_m2_K < cfg['heating']['h0_W_m2_K']
    # Take the last piece of a uniform mixed shell. The time-integrated area is
    # (r0+r1)*dt/2 for constant speed, rather than using the starting radius.
    r0, r1 = .045, .04508
    end, dt, done = advance_front(r0, r1, mixed.speed_m_s, 1e4)
    assert done and end == r1
    area_time = .5*(r0+r1)*dt
    field = np.array([[400.], [408.], [swept/mixed.speed_m_s]])
    removed = remap([r0,r1], field, [r1]).removed_integrals
    out = area_time * (mixed.char_products_kg_m2_s + mixed.surface_pyrolysis_gas_kg_m2_s)
    incoming = area_time * (mixed.convection_W_m2 + mixed.radiation_W_m2)
    outgoing = area_time * (mixed.conduction_into_solid_W_m2 + mixed.products_sensible_W_m2
                            + mixed.pyrolysis_W_m2 + mixed.char_removal_W_m2)
    mass_err = abs(out - sum(removed[:2])) / sum(removed[:2])
    energy_err = abs(incoming + removed[2] - outgoing) / (abs(incoming) + abs(removed[2]))
    assert mass_err < 1e-12 and energy_err < 1e-12
    paths = ['model/moving_surface_boundary.py','model/check_moving_surface_boundary.py',
             'model/moving_surface_thermochemistry.py','model/moving_surface_remap.py',
             'model/coupler.py','model/radial_model.py','configs/continuous_heating_campaign.json']
    result = dict(checked_utc=utc(), passed=True, sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                  for p in paths}, cases=['stationary virgin film-conduction','zero heat stationary virgin',
                  'isothermal pure-char energy-limited wall','mixed front with radiation and outgassing',
                  'integrated uniform mixed final shell with prescribed face state'],
                  max_face_balance_abs_W_m2=max(abs(x.energy_residual_W_m2) for x in (virgin,quiet,pure,mixed)),
                  final_shell_mass_relative_error=mass_err, final_shell_energy_relative_error=energy_err,
                  qualification='Manufactured local wall and remap checks. No transient wall integration, '
                   'independent motor prediction, native verification or physical event-time claim.')
    atomic(ROOT/'validation/moving_surface_boundary_verification.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

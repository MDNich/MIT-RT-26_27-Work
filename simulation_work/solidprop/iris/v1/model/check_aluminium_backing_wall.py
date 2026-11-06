"""Externally heated char/Al coupon compared with a sharp-transition enthalpy ODE."""
import json
import math

import numpy as np
from scipy.integrate import solve_ivp

from aluminium_phase_enthalpy import caloric, equilibrium
from aluminium_backing_wall import AluminiumBackingWall
from continuous_heating_campaign import digest
from moving_surface_thermochemistry import recover_temperature
from ops import ROOT, atomic, disks, host_check, utc
from radial_model import TABLE


POWER = 1500.  # W per radian per m, prescribed outside heat input


class Coupon(AluminiumBackingWall):
    def _outside(self, temp, conductance):
        return temp+POWER/conductance, -POWER, 0.


def reference(w, s, horizon):
    # Two control volumes. Integrate their *specific enthalpies* as independent
    # variables, with exact isothermal phase change on the backing. The near-
    # adiabatic hot film has a separately bounded energy contribution.
    rc, ri, ro = w.inner, w.interface, w.outer
    def centre(a,b):
        return a+(b-a)*(a+2.*b)/(3.*(a+b))
    rc_mid,ra_mid = centre(rc,ri), centre(ri,ro)
    mchar, mal = s.char[0], w.case_mass[0]
    def rhs(_, y):
        tc = float(recover_temperature(0.,1.,y[0]))
        ta = float(equilibrium(y[1])[0])
        kc = np.interp(tc,TABLE[:,0],TABLE[:,2])
        resistance = math.log(ri/rc_mid)/kc + math.log(ra_mid/ri)/w.case_k
        heat = (tc-ta)/resistance
        return [-heat/mchar, (heat+POWER)/mal]
    y0 = [s.enthalpy[0]/mchar,caloric(s.case_C[0],2.)[0]]
    sol = solve_ivp(rhs,(0.,horizon),y0,method='Radau',rtol=2e-10,atol=1e-5,dense_output=True)
    if not sol.success: raise RuntimeError(sol.message)
    return sol.sol


def main():
    disks()
    cfg = json.loads((ROOT/'configs/continuous_heating_campaign.json').read_text())['cases'][0]['configuration']
    g = cfg['geometry']
    ri = g['inner_radius_m']+.00030
    g.update(phenolic_outer_radius_m=ri,outer_radius_m=ri+.0008,phenolic_thickness_m=.00030,
             aluminium_thickness_m=.0008)
    cfg['char_law']['reactive_activity'] = 0.
    cfg['heating'].update(h0_W_m2_K=1e-6,gas_temperature_C=640.,hot_effective_emissivity=0.)
    horizon, results = 34., []
    for width,dt in [(4.,.16),(2.,.08),(1.,.04),(.5,.02)]:
        cfg['al_fusion_width_K'] = width
        w = Coupon(cfg,1,1)
        s = w.initial(640.,conversion=1.)
        ref = reference(w,s,horizon)
        initial_h = w.inventory(s)[1]
        peak_temp = peak_fraction = max_energy = film = 0.
        mixed_states = 0
        while s.time < horizon-1e-10:
            host_check()
            step = w.advance(s,min(dt,horizon-s.time))
            s = step.state
            film += step.film_heat
            current = w.phase(s.case_C)['mass_fraction_liquid']
            exact_t,exact_fraction = equilibrium(ref(s.time)[1])
            peak_temp = max(peak_temp,abs(float(exact_t)-s.case_C[0]))
            peak_fraction = max(peak_fraction,abs(float(exact_fraction)-current))
            mixed_states += 0. < current < 1.
            residual = abs(w.inventory(s)[1]-initial_h-POWER*s.time-film)
            max_energy = max(max_energy,residual)
        assert mixed_states>10 and current == 1. and s.liner_edges[0]==w.inner
        assert max_energy / (POWER*horizon) < 1e-7 and abs(film)<.001
        assert peak_temp < width+0.4 and peak_fraction < .015
        results.append(dict(width_K=width,dt_s=dt,maximum_Al_temperature_error_K=float(peak_temp),
                   maximum_liquid_fraction_error=float(peak_fraction),max_energy_residual_J=float(max_energy),
                   gas_film_energy_J=float(film),mixed_state_samples=int(mixed_states)))
    assert results[-1]['maximum_Al_temperature_error_K'] < results[0]['maximum_Al_temperature_error_K']
    assert results[-1]['maximum_liquid_fraction_error'] < results[0]['maximum_liquid_fraction_error']
    sources=['aluminium_backing_wall','aluminium_phase_enthalpy','moving_surface_transient',
             'check_aluminium_backing_wall','moving_surface_thermochemistry']
    atomic(ROOT/'validation/aluminium_backing_coupon.json',dict(checked_utc=utc(),passed=True,
        sources={name:digest(ROOT/f'model/{name}.py') for name in sources},runs=results,
        qualification='Fixed geometry, stationary pure char and pure Al. Two-cell sharp-phase ODE versus coupled wall under prescribed outside power. No motor event.'))
    print(json.dumps(results,indent=2))


if __name__ == '__main__':
    main()

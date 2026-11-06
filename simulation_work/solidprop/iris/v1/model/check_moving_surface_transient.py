"""Coupled verification from uniform rest through an exact moving-front event."""
import copy
import json
import math

import numpy as np

from continuous_heating_campaign import digest
from coupler import blowing, char_rate
from moving_surface_transient import Wall
from ops import ROOT, atomic, disks, host_check, utc


def run(w,s,ceiling,horizon):
    m0,h0 = w.inventory(s)
    history = []
    sums = np.zeros(10)
    mass_residual = energy_residual = peak_step_energy = 0.
    while s.time < horizon-1e-12 and len(s.virgin):
        if len(history)%100 == 0: host_check()
        a = w.advance(s,min(ceiling,horizon-s.time))
        s = a.state
        history.append([s.time,a.face_C,a.case_interface_C,a.speed,float(s.liner_edges[0])])
        sums += [a.bulk_gas,a.face_gas,a.char_products,a.film_heat,a.radiation_heat,a.outer_loss,
                 a.bulk_reaction,a.bulk_gas_heat,a.face_reaction,a.face_products_heat]
        m,h = w.inventory(s)
        mass_residual = max(mass_residual,abs(m+sum(sums[:3])-m0)/m0)
        balance = h-h0-sums[3]-sums[4]+sum(sums[5:])
        energy_residual = max(energy_residual,abs(balance)/max(1.,abs(h0),abs(sums[3])+abs(sums[4])))
        peak_step_energy = max(peak_step_energy,abs(a.energy_error))
    assert mass_residual < 1e-9 and energy_residual < 1e-7
    return s,np.array(history),dict(steps=len(history),max_cumulative_mass_relative_error=mass_residual,
             max_cumulative_energy_relative_error=energy_residual,max_step_energy_error_J_per_rad_m=peak_step_energy)


def main():
    disks()
    cfg = json.loads((ROOT/'configs/continuous_heating_campaign.json').read_text())['cases'][0]['configuration']
    # With no activity, initially pure char and equal ambient, gas and solid
    # temperatures, all fluxes vanish and the mesh should be stationary.
    quiet = copy.deepcopy(cfg)
    quiet['char_law']['reactive_activity'] = 0.
    quiet['heating'].update(gas_temperature_C=22.,radiative_temperature_C=22.)
    w = Wall(quiet,20,5)
    s = w.initial(conversion=1.)
    end,z,stationary = run(w,s,.17,1.51)
    assert max(abs(z[:,1]-22.))<1e-8 and np.array_equal(s.liner_edges,end.liner_edges)
    assert np.allclose(s.enthalpy,end.enthalpy,rtol=0,atol=1e-8)

    # In a uniform, pure-char isothermal wall the net surface power exactly
    # pays the char cost, so the moving speed is constant and known a priori.
    t = 1150.
    pure = copy.deepcopy(cfg)
    law = pure['char_law']
    flux = char_rate(t,law)
    film = blowing(pure['heating']['h0_W_m2_K'],flux,pure['heating']['gas_cp_J_kg_K'])
    pure['heating'].update(ambient_temperature_C=t,gas_temperature_C=t+flux*law['effective_endothermic_cost_J_kg']/film)
    speed = flux/pure['material']['char_reference_density_kg_m3']
    fixtures = []
    for n,dt in [(17,.67),(43,.171)]:
        w = Wall(pure,n,8)
        exact = (w.interface-w.inner)/speed
        end,z,metrics = run(w,w.initial(t,1.),dt,1.2*exact)
        assert end.liner_edges.tolist()==[w.interface] and all(len(x)==0 for x in (end.virgin,end.char,end.enthalpy))
        assert max(abs(z[:,1]-t))<1e-7 and max(abs(z[:,2]-t))<1e-7
        assert max(abs(z[:,4]-w.inner-speed*z[:,0]))<2e-12 and abs(end.time-exact)<2e-8
        fixtures.append(dict(cells=n,step_ceiling_s=dt,analytic_event_s=exact,
                             coupled_event_s=end.time,max_temperature_departure_K=float(max(abs(z[:,1]-t))),**metrics))

    # Reacting mixed coupon, genuinely nonuniform temperature. Use a thinner
    # synthetic liner for verification, with the inherited CF thermal backing.
    # Compare three time resolutions at fixed mesh and independent mass/energy sums.
    mixed = copy.deepcopy(json.loads((ROOT/'configs/continuous_heating_campaign.json').read_text())['cases'][1]['configuration'])
    g = mixed['geometry']
    g.update(phenolic_thickness_m=.00016,phenolic_outer_radius_m=g['inner_radius_m']+.00016,
             outer_radius_m=g['inner_radius_m']+.00016+g['aluminium_thickness_m'])
    seq = []
    for dt in (.08,.04,.02):
        w = Wall(mixed,18,8)
        end,z,metrics = run(w,w.initial(350.,.2),dt,40.)
        assert not len(end.char) and max(z[:,1])-min(z[:,1])>100.
        seq.append(dict(step_ceiling_s=dt,coupled_event_s=end.time,
                        terminal_inner_casing_cell_C=float(end.case_C[0]),**metrics))
    delta = np.abs(np.diff([r['coupled_event_s'] for r in seq]))
    assert delta[1]<delta[0] and delta[1] < .015*seq[-1]['coupled_event_s']
    sources = ['moving_surface_transient','check_moving_surface_transient','moving_surface_boundary',
               'moving_surface_conduction','moving_surface_remap','moving_surface_thermochemistry','radial_model','coupler']
    receipt = dict(checked_utc=utc(),passed=True,sources={s:digest(ROOT/f'model/{s}.py') for s in sources},
                   plan_sha256=digest(ROOT/'configs/continuous_heating_campaign.json'),
                   stationary=stationary,isothermal_char=fixtures,nonuniform_mixed_coupon=seq,
                   qualification='Manufactured independent coupled tests only. Coupon times are not Iris motor results.')
    atomic(ROOT/'validation/moving_surface_transient_verification.json',receipt)
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':
    main()

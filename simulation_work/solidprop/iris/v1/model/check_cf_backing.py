"""Independently integrate the coupled temperature and competing-channel coupon ODE."""
import json
import math
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from cf_backing_response import (A, CHI, DENSITY_LOSS, E, GAS_CP, HEAT_PER_GAS, N, RESIDUE_CP,
                                 RGAS, VIRGIN_CP, conductivity, mixture, primitive)
from cf_backing_wall import CarbonBackingWall
from continuous_heating_campaign import digest
from moving_surface_thermochemistry import recover_temperature
from ops import ROOT, atomic, disks, host_check, utc
from radial_model import TABLE

POWER = 1500.
HORIZON = 28.


class Coupon(CarbonBackingWall):
    def _outside(self,t,g):
        return t+POWER/g,-POWER,0.


def reference(w,s):
    rin,ri,ro = w.inner,w.interface,w.outer
    def centre(a,b):
        return (2./3.)*(b*b+a*b+a*a)/(a+b)
    rchar,rcase = centre(rin,ri),centre(ri,ro)
    def rhs(_,v):
        temp,back,a,b = v
        progress = np.array([a,b])
        rate = A*np.exp(-E/(RGAS*(back+273.15)))*max(0.,1.-a-b)**N
        rate[1] *= 1.+w.cfg['cf_catalyst']*b
        extent = CHI@progress
        dg = DENSITY_LOSS*CHI*rate
        h,cp = mixture(back,extent)
        hgas = primitive(back,GAS_CP,1000.)[0]
        dh_mix = primitive(back,RESIDUE_CP,1000.)[0]-primitive(back,VIRGIN_CP,300.)[0]
        m = w.original_mass[0]*(1.-DENSITY_LOSS*extent)
        kchar = np.interp(temp,TABLE[:,0],TABLE[:,2])
        g = 1./(math.log(ri/rchar)/kchar+math.log(rcase/ri)/conductivity(back,extent))
        power = g*(temp-back)
        tempdot = -power/(s.char[0]*np.interp(temp,TABLE[:,0],TABLE[:,4]))
        reactive = w.original_mass[0]*(HEAT_PER_GAS@dg+sum(dg)*(h-hgas))
        backdot = (power+POWER+reactive-m*dh_mix*(CHI@rate))/(m*cp)
        return [tempdot,backdot,*rate]
    sol=solve_ivp(rhs,(0,HORIZON),(340.,340.,0.,0.),method='Radau',rtol=1e-9,atol=1e-11,dense_output=True)
    if not sol.success: raise RuntimeError(sol.message)
    return sol.sol


def main():
    disks()
    configs=json.loads((ROOT/'configs/continuous_heating_campaign.json').read_text())['cases']
    cfg=next(c['configuration'] for c in configs if c['configuration']['case_material']=='cf')
    g=cfg['geometry']
    g['phenolic_outer_radius_m']=g['inner_radius_m']+.00030
    g.update(outer_radius_m=g['phenolic_outer_radius_m']+.0008,phenolic_thickness_m=.00030,aluminium_thickness_m=.0008)
    cfg['char_law']['reactive_activity']=0.
    cfg['heating'].update(h0_W_m2_K=1e-6,gas_temperature_C=340.,hot_effective_emissivity=0.)
    cfg['cf_catalyst']=7.4886
    w=Coupon(cfg,1,1)
    exact=reference(w,w.initial(340.,conversion=1.))
    records=[]
    for dt in (.08,.04,.02,.01):
        w=Coupon(cfg,1,1)
        s=w.initial(340.,conversion=1.)
        p=np.zeros((2,1))
        h0=w.inventory(s)[1]
        gas=expelled=reaction=film=peak_e=peak_t=peak_x=peak_m=0.
        while s.time<HORIZON-1e-10:
            if int(s.time/dt)%64==0: host_check()
            step=w.coupled_step(s,p,min(dt,HORIZON-s.time))
            s,p=step.thermal.state,step.paths
            gas+=step.backing_gas
            expelled+=step.backing_gas_heat
            reaction+=step.backing_reaction_heat
            film+=step.thermal.film_heat
            ref=exact(s.time)
            tchar=float(recover_temperature(s.virgin,s.char,s.enthalpy)[0])
            peak_t=max(peak_t,abs(s.case_C[0]-ref[1]),abs(tchar-ref[0]))
            peak_x=max(peak_x,max(abs(p[:,0]-ref[2:])))
            peak_m=max(peak_m,abs(w.case_mass[0]+gas-w.original_mass[0]))
            peak_e=max(peak_e,abs(w.inventory(s)[1]-h0+expelled-reaction-POWER*s.time-film))
        assert p.sum()>.9 and abs(film)<.001 and peak_m<1e-10 and peak_e/(POWER*HORIZON)<1e-6
        records.append(dict(dt_s=dt,max_temperature_error_K=float(peak_t),max_channel_fraction_error=float(peak_x),
                            max_energy_error_J=float(peak_e),max_mass_error_kg=float(peak_m),
                            exit_gas_kg=float(gas),terminal_paths=p.ravel().tolist()))
    assert records[-1]['max_temperature_error_K']<.5 and records[-1]['max_channel_fraction_error']<.003
    assert all(b['max_temperature_error_K']<.7*a['max_temperature_error_K'] for a,b in zip(records,records[1:]))
    names=('cf_backing_response','cf_backing_wall','diagnose_cf_backing','check_cf_backing')
    atomic(ROOT/'validation/cf_backing_coupon.json',dict(passed=True,utc=utc(),records=records,
           sources={n:digest(ROOT/'model'/(n+'.py')) for n in names},
           scope='Fixed char and oxygen-free CF coupon, two cells, prescribed outer heat. Independent temperature-form Radau ODE.'))
    print(records[-1])


if __name__=='__main__': main()

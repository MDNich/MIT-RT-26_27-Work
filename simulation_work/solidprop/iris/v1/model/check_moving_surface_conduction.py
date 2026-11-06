"""Manufactured layered steady and transient annular conduction verification."""
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.special import j0, y0

from moving_surface_conduction import thermal_geometry, implicit_step
from ops import ROOT, atomic, disks, utc


def layered():
    edges = np.r_[np.linspace(.041, .045, 14), np.linspace(.045,.05, 9)[1:]]
    k = np.where(edges[1:]<=.045,.41,136.)
    c, v, g = thermal_geometry(edges,k)
    q = 800./(np.log(.045/.041)/.41+np.log(.05/.045)/136.)
    exact = 822.-q*(np.log(np.minimum(c,.045)/.041)/.41+np.log(np.maximum(c,.045)/.045)/136.)
    temp, flux = implicit_step(exact, v*1.7e6, .7, g, np.zeros(len(c)),822.,22.)
    assert np.max(abs(temp-exact)) < 1e-10
    assert np.max(abs(flux-q))/q < 1e-11
    # In a single insulated cell all supplied power goes into stored heat.
    t,f = implicit_step([50.],[3.],.25,[8.,9.],[600.])
    assert t[0] == 100. and np.all(f==0)
    # An insulated nonuniform layer redistributes energy internally.
    old = np.where(c<.045,600.,22.)
    cap = v*np.where(c<.045,1.1e6,2.42e6)
    t,f = implicit_step(old,cap,2.,g,np.zeros(len(c)))
    residual = abs(np.dot(cap,t-old))/np.dot(cap,old)
    assert residual < 1e-13 and f[0] == f[-1] == 0
    return dict(log_solution_max_temperature_error_K=float(max(abs(temp-exact))),
                log_solution_max_flux_relative_error=float(max(abs(flux-q))/q),
                insulated_energy_relative_error=residual)


def transient():
    # First annular Dirichlet eigenmode with exact continuum amplitude decay.
    r0,r1,k,vol_cp = .04,.05,.6,1.25e6
    mode = lambda z,r: j0(z*r)*y0(z*r0)-y0(z*r)*j0(z*r0)
    wave = brentq(lambda z: mode(z,r1),200.,400.)
    rate = wave**2*k/vol_cp
    endpoint = 1./rate
    def solve(n,steps):
        r = np.linspace(r0,r1,n+1)
        c,v,g = thermal_geometry(r,np.full(n,k))
        shape = mode(wave,c)
        amp = 100.*shape/shape[np.argmax(abs(shape))]
        old = 22.+amp
        src = np.zeros(n)
        energy_in = 0.
        for _ in range(steps):
            t,f = implicit_step(old,v*vol_cp,endpoint/steps,g,src,22.,22.)
            energy_in += (f[0]-f[-1])*endpoint/steps
            old = t
        error = t-22.-amp/np.e
        ledger = abs(np.dot(v*vol_cp,t-(22.+amp))-energy_in)/abs(energy_in)
        assert ledger < 1e-11
        return error
    # Resolve temporal and spatial error separately. For the space check use
    # Richardson elimination of leading backward-Euler time error at each mesh.
    spatial = []
    for n in (16,32,64):
        coarse = solve(n,2048)
        fine = solve(n,4096)
        spatial.append(dict(cells=n,max_error_K_4096=float(max(abs(fine))),
                            time_extrapolated_error_K=float(max(abs(2*fine-coarse)))))
    temporal = [dict(steps=n,max_error_K=float(max(abs(solve(320,n))))) for n in (16,32,64)]
    assert all(a['time_extrapolated_error_K'] / b['time_extrapolated_error_K'] > 3.5
               for a,b in zip(spatial,spatial[1:]))
    assert all(1.8 < a['max_error_K']/b['max_error_K'] < 2.1 for a,b in zip(temporal,temporal[1:]))
    return dict(annular_wavenumber_per_m=wave,physical_test_duration_s=endpoint,
                fixed_mesh_320_time_refinement=temporal,space_refinement=spatial)


def main():
    disks()
    paths = [ROOT/'model/moving_surface_conduction.py',Path(__file__)]
    result = dict(checked_utc=utc(),passed=True,sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in paths},steady=layered(),transient=transient(),
                  scope='Stationary-geometry finite-volume conduction component with frozen properties. '
                        'Thermochemical and moving-front integration is a separate gate.')
    atomic(ROOT/'validation/moving_surface_conduction_verification.json',result)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()

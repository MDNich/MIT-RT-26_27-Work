"""Independent conservative transient annular wall. Quantities per radian/metre.

The nonlinear solve evaluates temperature, reaction, blowing and boundary
power together on the old mesh. A subsequent conservative geometric update
sweeps the reacted inventory at its end-of-step temperature. Backward Euler
and that split limit the scheme to first order in time.
"""
from dataclasses import dataclass
import math

import numpy as np
from scipy.linalg import solve_banded
from scipy.optimize import brentq

from moving_surface_boundary import solve_face
from moving_surface_conduction import thermal_geometry
from moving_surface_remap import remap
from moving_surface_thermochemistry import Chemistry, REFERENCE_C, TEMPERATURE, recover_temperature, sensible
from radial_model import R, SIGMA, TABLE


class Cutback(RuntimeError):
    """Retry the same accepted state with a shorter interval."""


@dataclass(frozen=True)
class State:
    time: float
    liner_edges: np.ndarray
    virgin: np.ndarray
    char: np.ndarray
    enthalpy: np.ndarray
    case_C: np.ndarray


@dataclass(frozen=True)
class Step:
    state: State
    dt: float
    face_C: float
    case_interface_C: float
    outer_C: float
    speed: float
    bulk_gas: float
    face_gas: float
    char_products: float
    film_heat: float
    radiation_heat: float
    outer_loss: float
    bulk_reaction: float
    bulk_gas_heat: float
    face_reaction: float
    face_products_heat: float
    swept_enthalpy: float
    mass_error: float
    energy_error: float
    iterations: int
    cutbacks: int


class Wall:
    def __init__(self, cfg, liner_cells, case_cells):
        if min(liner_cells, case_cells) < 1:
            raise ValueError('A liner and a casing are required')
        self.cfg = cfg
        self.chem = Chemistry.from_config(cfg)
        self.heating = cfg['heating']
        if 'pulse_duration_s' in self.heating:
            raise ValueError('This candidate is for continuous imposed heating')
        g = cfg['geometry']
        self.inner, self.interface, self.outer = (g[k] for k in ('inner_radius_m','phenolic_outer_radius_m','outer_radius_m'))
        if not 0 < self.inner < self.interface < self.outer:
            raise ValueError('Inconsistent radial geometry')
        self.n = liner_cells
        self.pitch = (self.interface-self.inner)/liner_cells
        self.case_edges = np.linspace(self.interface,self.outer,case_cells+1)
        m = cfg['material']
        self.rho = m['virgin_reference_density_kg_m3']
        self.case_k = cfg['cf_radial_k'] if cfg['case_material']=='cf' else m['aluminium_conductivity_W_m_K']
        self.case_mass = m['aluminium_density_kg_m3'] * np.diff(self.case_edges) * (self.case_edges[1:]+self.case_edges[:-1])/2.
        self.variable_cp = cfg['case_material']=='cf' and 'cf_cp_constant_J_kg_K' not in cfg
        self.constant_cp = cfg.get('cf_cp_constant_J_kg_K',m['aluminium_heat_capacity_J_kg_K'])
        self.scale = cfg.get('cf_cp_scale',1.)

    def casing(self, t):
        """Specific h and cp of the explicitly retained backing surrogate."""
        if self.variable_cp:
            # Primitive of clip(T,20,200); derivative is the inherited cp.
            primitive = lambda z: 20.*z + .5*np.maximum(z-20.,0.)**2 - .5*np.maximum(z-200.,0.)**2
            h = 687.31*(t-REFERENCE_C) + 2.8773*(primitive(t)-primitive(REFERENCE_C))
            cp = 687.31 + 2.8773*np.clip(t,20.,200.)
        else:
            h, cp = self.constant_cp*(t-REFERENCE_C), np.full_like(t,self.constant_cp)
        return self.scale*h, self.scale*cp

    def initial(self, temperature_C=None, conversion=0.):
        if not 0 <= conversion <= 1:
            raise ValueError('Conversion must be a fraction')
        t = self.cfg['initial_temperature_C'] if temperature_C is None else temperature_C
        edges = np.linspace(self.inner,self.interface,self.n+1)
        m = self.rho*np.diff(edges)*(edges[1:]+edges[:-1])/2.
        v,c = m*(1.-conversion), m*self.chem.char_yield*conversion
        hv,hc = sensible(t)
        return State(0.,edges,v,c,v*hv+c*hc,np.full(len(self.case_mass),t,dtype=float))

    def inventory(self,s):
        return float(sum(s.virgin+s.char)), float(sum(s.enthalpy)+self.case_mass@self.casing(s.case_C)[0])

    def _outside(self, t, conductance):
        """Surface temperature and net heat leaving, with the outer half-cell."""
        h, r = self.heating, self.outer
        ambient, film, eps = h['ambient_temperature_C'],h['outer_h_W_m2_K'],h['outer_emissivity']
        def loss(z):
            return r*(film*(z-ambient) + eps*SIGMA*((z+273.15)**4-(ambient+273.15)**4))
        wall = t if t==ambient else brentq(lambda z: conductance*(t-z)-loss(z),min(t,ambient),max(t,ambient))
        deriv = r*(film+4*eps*SIGMA*(wall+273.15)**3)
        return wall, loss(wall), deriv/(1.+deriv/conductance)

    def _thermal(self,s,dt):
        n = len(s.virgin)
        edges = np.r_[s.liner_edges[:-1],self.case_edges]
        old = np.r_[recover_temperature(s.virgin,s.char,s.enthalpy),s.case_C]
        t = old.copy()
        material = self.chem
        y, lp = material.char_yield, material.pyrolysis_J_per_kg_virgin
        r = edges[0]
        face_area = r
        old_case_h = self.casing(s.case_C)[0]
        face_slope = None
        for it in range(1,33):
            mid = .5*(old[:n]+t[:n])
            kelvin = mid+273.15
            kdt = dt*333.*np.exp(-64081./(R*kelvin))
            lost = s.virgin*(-np.expm1(-kdt))
            v, c = s.virgin-lost, s.char+y*lost
            gas = (1.-y)*lost
            alpha = c/(c+y*v)
            k = (1.-alpha)*np.interp(t[:n],TABLE[:,0],TABLE[:,1]) + alpha*np.interp(t[:n],TABLE[:,0],TABLE[:,2])
            centres,vol,g = thermal_geometry(edges,np.r_[k,np.full(len(self.case_mass),self.case_k)])
            solid = sensible(t[:n])
            h = v*solid[:,0]+c*solid[:,1]
            hg = material.gas_cp_J_kg_K*(mid-REFERENCE_C)
            case_h,case_cp = self.casing(t[n:])
            storage = np.r_[h-s.enthalpy+lp*lost+gas*hg,self.case_mass*(case_h-old_case_h)]
            bulk_flux = float(sum(gas))/(dt*face_area)
            face = solve_face(t[0],v[0]/vol[0],c[0]/vol[0],r,centres[0],bulk_flux,self.cfg)
            mean_r = r+.5*face.speed_m_s*dt
            q = np.empty(len(t)+1)
            # Same time-integrated face area for products, film and conduction.
            q[0] = mean_r*face.conduction_into_solid_W_m2
            q[1:-1] = g[1:-1]*(t[:-1]-t[1:])
            outer, q[-1], d_outer = self._outside(t[-1],g[-1])
            residual = storage-dt*(q[:-1]-q[1:])
            cpv = np.interp(t[:n],TABLE[:,0],TABLE[:,3])
            cpc = np.interp(t[:n],TABLE[:,0],TABLE[:,4])
            d_lost = s.virgin*np.exp(-kdt)*kdt*64081./(2.*R*kelvin**2)
            cap = np.r_[v*cpv+c*cpc+d_lost*(y*solid[:,1]-solid[:,0]+lp+(1.-y)*hg)
                        + .5*gas*material.gas_cp_J_kg_K,self.case_mass*case_cp]
            # Per-cell equation error expressed as an equivalent temperature.
            if max(abs(residual)/cap) < 2e-7 and abs(mean_r-face_area) <= 1e-11*r:
                interface = t[n]+q[n]*math.log(centres[n]/self.interface)/self.case_k
                return dict(virgin=v,char=c,enthalpy=h,gas=float(sum(gas)),bulk_reaction=float(sum(lp*lost)),
                            gas_heat=float(gas@hg),case_C=t[n:],face=face,outer=outer,outer_loss=q[-1],
                            interface=interface,volume=vol[:n],iterations=it,
                            conversion_increment=float(max(lost/(s.virgin+s.char/y))))
            # Local diagonal approximation to the film/reaction derivative.
            # Nonlocal blowing, angular geometry and variable k are refreshed
            # on each nonlinear residual evaluation.
            if np.any(cap<=0):
                raise Cutback('Nonpositive effective heat capacity')
            diagonal = cap/dt
            if face_slope is None:
                perturb = .01 if t[0]+.01 <= TEMPERATURE[-1] else -.01
                adjacent = solve_face(t[0]+perturb,v[0]/vol[0],c[0]/vol[0],r,centres[0],bulk_flux,self.cfg)
                face_slope = max(0.,(face.conduction_into_solid_W_m2-adjacent.conduction_into_solid_W_m2)/perturb)
            diagonal[0] += mean_r*face_slope
            diagonal[-1] += d_outer
            diagonal[:-1] += g[1:-1]
            diagonal[1:] += g[1:-1]
            a = np.zeros((3,len(t)))
            a[1] = diagonal
            a[0,1:] = a[2,:-1] = -g[1:-1]
            correction = solve_banded((1,1),a,-residual/dt)
            damping = min(1., 180./max(max(abs(correction)),1.))
            t = t+damping*correction
            if min(t[:n]) < TEMPERATURE[0] or max(t[:n]) > TEMPERATURE[-1] or not np.all(np.isfinite(t)):
                raise Cutback('Trial temperature outside supported enthalpy interval')
            face_area = mean_r
        raise Cutback('Wall iteration failed its local energy tolerance')

    def advance(self,s,requested_dt):
        if not len(s.virgin) or not math.isfinite(requested_dt) or requested_dt <= 0:
            raise ValueError('Expected positive duration and remaining liner')
        radius = s.liner_edges[0]
        width = self.interface-radius
        dt = requested_dt
        initial_mass, initial_h = self.inventory(s)
        for cuts in range(30):
            try:
                trial = self._thermal(s,dt)
                motion = trial['face'].speed_m_s*dt
                if trial['conversion_increment'] > .05 or (len(s.virgin)>1 and motion>.4*np.diff(s.liner_edges[:2])[0]):
                    raise Cutback('Reaction or front increment too large')
                done = motion >= width
                if done:
                    def gap(interval):
                        if interval == 0: return -width
                        return self._thermal(s,interval)['face'].speed_m_s*interval-width
                    dt = brentq(gap,0.,dt,xtol=2e-13)
                    trial = self._thermal(s,dt)
                # Keep the undisturbed cells fixed. Merge the front remnant
                # with its neighbour at half pitch, preserving both inventories.
                new_r = self.interface if done else radius+trial['face'].speed_m_s*dt
                done = new_r == self.interface
                if done:
                    edges = np.array([self.interface])
                else:
                    first = 2 if len(s.virgin)>1 and s.liner_edges[1]-new_r < .5*self.pitch else 1
                    edges = np.r_[new_r,s.liner_edges[first:]]
                fields = np.vstack([trial['virgin'],trial['char'],trial['enthalpy']])
                if np.array_equal(edges,s.liner_edges):
                    fields_new, swept_h = fields, 0.
                else:
                    transfer = remap(s.liner_edges,fields/trial['volume'],edges)
                    fields_new, swept_h = transfer.cell_integrals, transfer.removed_integrals[2]
                state = State(s.time+dt,edges,*fields_new,trial['case_C'])
                break
            except Cutback:
                dt *= .5
        else:
            raise RuntimeError('Moving-wall step exhausted cutbacks')

        face = trial['face']
        area_time = .5*(radius+new_r)*dt
        gas_f = area_time*face.surface_pyrolysis_gas_kg_m2_s
        char_f = area_time*face.char_products_kg_m2_s
        film, rad = area_time*face.convection_W_m2, area_time*face.radiation_W_m2
        outer_loss = dt*trial['outer_loss']
        reaction_f = area_time*(face.pyrolysis_W_m2+face.char_removal_W_m2)
        products_h = area_time*face.products_sensible_W_m2
        final_mass, final_h = self.inventory(state)
        mass_error = final_mass-initial_mass+gas_f+char_f+trial['gas']
        energy_error = (final_h-initial_h-film-rad+outer_loss+products_h+reaction_f
                        +trial['bulk_reaction']+trial['gas_heat'])
        # Verify the remap export independently against the mass fluxes used by
        # the boundary. Swept sensible enthalpy cancels in the full balance.
        if abs(mass_error) > 5e-11*max(initial_mass,1e-4):
            raise RuntimeError(f'Mass closure failed: {mass_error:g}')
        if abs(swept_h-area_time*face.swept_solid_sensible_W_m2) > 2e-7*max(1.,abs(swept_h)):
            raise RuntimeError('Sweep and face enthalpy disagree')
        if abs(energy_error) > 2e-6*max(1.,abs(film)+abs(rad)+abs(outer_loss)):
            raise RuntimeError(f'Energy closure failed: {energy_error:g}')
        return Step(state,dt,face.temperature_C,trial['interface'],trial['outer'],face.speed_m_s,
                    trial['gas'],gas_f,char_f,film,rad,outer_loss,trial['bulk_reaction'],
                    trial['gas_heat'],reaction_f,products_h,swept_h,mass_error,energy_error,trial['iterations'],cuts)

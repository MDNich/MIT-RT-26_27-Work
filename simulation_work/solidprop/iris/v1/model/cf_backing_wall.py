"""Carbon backing with competing reactions, open-system heat and spatially varying conductivity.

The original wall kernel is sealed by earlier campaigns. The thermal iteration
below retains its face/liner balance and evaluates the local CF conductivity and
interface half-cell resistance with the frozen conversion at each iteration.
Thermal and reaction operators are split in time; the campaign refines that step.
"""
from dataclasses import dataclass, replace
import math

import numpy as np
from scipy.linalg import solve_banded

from cf_backing_response import CHI, DENSITY_LOSS, VIRGIN_DENSITY, conductivity, mixture, react
from moving_surface_boundary import solve_face
from moving_surface_conduction import thermal_geometry
from moving_surface_thermochemistry import REFERENCE_C, TEMPERATURE, recover_temperature, sensible
from moving_surface_transient import Cutback, Wall
from radial_model import R, TABLE


@dataclass
class BackingStep:
    thermal: object
    paths: np.ndarray
    backing_gas: float
    backing_gas_heat: float
    backing_reaction_heat: float


class CarbonBackingWall(Wall):
    def __init__(self,cfg,liner_cells,case_cells):
        if cfg['case_material']!='cf': raise ValueError('CF case required')
        super().__init__(cfg,liner_cells,case_cells)
        self.original_mass = VIRGIN_DENSITY*np.diff(self.case_edges)*(self.case_edges[1:]+self.case_edges[:-1])/2.
        self.activate(np.zeros((2,case_cells)))

    def activate(self, paths):
        self.extent = CHI@paths
        self.case_mass = self.original_mass*(1.-DENSITY_LOSS*self.extent)

    def casing(self,t):
        return mixture(t,self.extent)

    def k_case(self,t):
        return conductivity(t,self.extent)

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
            case_k = self.k_case(t[n:])
            centres,vol,g = thermal_geometry(edges,np.r_[k,case_k])
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
                interface = t[n]+q[n]*math.log(centres[n]/self.interface)/case_k[0]
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

    def coupled_step(self,s,paths,dt):
        # The accepted thermal interval may be shortened at liner events.
        # Stage the subsequent local reaction on that exact duration. A failed
        # reaction or excessive conversion retries from the untouched state.
        self.activate(paths)
        for _ in range(24):
            thermal = self.advance(s,dt)
            trial = thermal.state
            try:
                reaction = react(trial.case_C,paths,thermal.dt,self.cfg['cf_catalyst'])
                if np.max((reaction.paths-paths).sum(axis=0))>.04:
                    raise ArithmeticError('CF increment exceeded 0.04')
            except ArithmeticError:
                dt = .5*thermal.dt
                continue
            corrected = replace(trial,case_C=reaction.temperature)
            self.activate(reaction.paths)
            # The solved face fluxes belong to the transport portion. For
            # reports reconstruct casing surface temperatures after reaction.
            if len(corrected.virgin):
                lt = recover_temperature(corrected.virgin,corrected.char,corrected.enthalpy)
                y = self.chem.char_yield
                alpha = corrected.char/(corrected.char+y*corrected.virgin)
                kl = (1.-alpha)*np.interp(lt,TABLE[:,0],TABLE[:,1])+alpha*np.interp(lt,TABLE[:,0],TABLE[:,2])
                ck = self.k_case(corrected.case_C)
                edges = np.r_[corrected.liner_edges[:-1],self.case_edges]
                centres,_,conductance = thermal_geometry(edges,np.r_[kl,ck])
                n = len(lt)
                flux = conductance[n]*(lt[-1]-corrected.case_C[0])
                interface = corrected.case_C[0]+flux*math.log(centres[n]/self.interface)/ck[0]
            else:
                # At the event, report the left-limit face from the transport
                # solve; direct gas exposure of the now-bare casing is outside this run.
                interface = thermal.case_interface_C
                _,_,conductance = thermal_geometry(self.case_edges,self.k_case(corrected.case_C))
            outer = self._outside(corrected.case_C[-1],conductance[-1])[0]
            return BackingStep(replace(thermal,state=corrected,case_interface_C=interface,outer_C=outer),
                               reaction.paths,float(self.original_mass@reaction.gas),
                               float(self.original_mass@reaction.gas_heat),float(self.original_mass@reaction.reaction_heat))
        raise RuntimeError('CF coupling exhausted cutbacks')

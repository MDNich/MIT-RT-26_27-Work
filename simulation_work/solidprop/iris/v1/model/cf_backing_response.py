"""Conservative local T700/M21 surrogate, per kg of original composite.

Reference enthalpies are zero at 22 C. DSC heats follow the signed gas-mass
source of Part II (equations 6--8). All gas leaves at its local formation
temperature. Geometry and oxygen-free conditions are imposed.
"""
from dataclasses import dataclass

import numpy as np

from diagnose_cf_backing import A, CHI, DENSITY_LOSS, E, N, RGAS
from moving_surface_thermochemistry import REFERENCE_C

VIRGIN_DENSITY = 1575.
HEAT_PER_GAS = np.array([259540., -152220.])
VIRGIN_CP = np.array([687.31,2.8773])
RESIDUE_CP = np.array([662.53,2.599,-2.0761e-3,5.1327e-7])
GAS_CP = np.array([1256.6,1.0610,-9.2485e-4,3.5977e-7])
VIRGIN_K = np.array([.61391,.0011113])
RESIDUE_K = np.array([.077211,.00023397,-4.1903e-7,7.4228e-10])


def primitive(t, coeffs, high):
    """Integrate the endpoint-held polynomial, including outside its measured interval."""
    clipped = np.clip(t,20.,high)
    cp = np.polynomial.polynomial.polyval(clipped,coeffs)
    integral = np.polynomial.polynomial.polyint(coeffs)
    enthalpy = np.polynomial.polynomial.polyval(clipped,integral) - np.polynomial.polynomial.polyval(REFERENCE_C,integral)
    return enthalpy + (t-clipped)*cp,cp


def mixture(t, extent):
    h0,cp0 = primitive(t,VIRGIN_CP,300.)
    h1,cp1 = primitive(t,RESIDUE_CP,1000.)
    return (1.-extent)*h0+extent*h1,(1.-extent)*cp0+extent*cp1


def conductivity(t,extent):
    kv = np.polynomial.polynomial.polyval(np.clip(t,20.,150.),VIRGIN_K)
    kd = np.polynomial.polynomial.polyval(np.clip(t,20.,1000.),RESIDUE_K)
    return (1.-extent)*kv+extent*kd


def advance_paths(t, paths, dt, catalyst, midpoint_paths=None):
    """Exponential competing hazards share a single nonnegative remaining pool."""
    mid = paths if midpoint_paths is None else midpoint_paths
    left = np.maximum(0.,1.-paths.sum(axis=0))
    middle = np.maximum(0.,1.-mid.sum(axis=0))
    hazards = A[:,None]*np.exp(-E[:,None]/(RGAS*(t+273.15)))*middle**(N[:,None]-1.)
    hazards[1] *= 1.+catalyst*mid[1]
    total = hazards.sum(axis=0)
    used = left*(-np.expm1(-dt*total))
    return paths+hazards*np.divide(used,total,out=np.zeros_like(used),where=total>0.)


@dataclass
class Reaction:
    temperature: np.ndarray
    paths: np.ndarray
    gas: np.ndarray
    gas_heat: np.ndarray
    reaction_heat: np.ndarray


def react(t0,paths,dt,catalyst):
    """Adiabatic reaction advance. Solid enthalpy, signed reaction heat and gas close locally."""
    ext0 = CHI@paths
    h0 = (1.-DENSITY_LOSS*ext0)*mixture(t0,ext0)[0]
    mid_t = t0.copy()
    mid_p = paths
    for _ in range(16):
        end = advance_paths(mid_t,paths,dt,catalyst,mid_p)
        loss = DENSITY_LOSS*CHI[:,None]*(end-paths)
        gas = loss.sum(axis=0)
        reaction_heat = HEAT_PER_GAS@loss
        gas_heat = gas*primitive(mid_t,GAS_CP,1000.)[0]
        extent = CHI@end
        retained = 1.-DENSITY_LOSS*extent
        wanted = (h0+reaction_heat-gas_heat)/retained
        temperature = mid_t.copy()
        for _ in range(10):
            h,cp = mixture(temperature,extent)
            correction = (wanted-h)/cp
            temperature += correction
            if np.max(abs(correction))<2e-10: break
        else: raise ArithmeticError('CF caloric inversion failed')
        next_t = .5*(t0+temperature)
        next_p = .5*(paths+end)
        if np.max(abs(next_t-mid_t))<2e-8 and np.max(abs(next_p-mid_p))<1e-10:
            if np.max(abs(retained*mixture(temperature,extent)[0]-h0-reaction_heat+gas_heat))>2e-5:
                raise ArithmeticError('Unclosed local CF enthalpy')
            return Reaction(temperature,end,gas,gas_heat,reaction_heat)
        mid_t,mid_p = next_t,next_p
    raise ArithmeticError('CF reaction did not converge')

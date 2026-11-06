"""Local, quasi-steady candidate hot-face closure for continuous gas exposure.

All heat fluxes are per current hot-face area. The adjacent cell supplies its
temperature, partial mass densities and radius. The rest of the wall is a
separate transient problem. Material swept by the front completes pyrolysis
and the resulting char is consumed at the same face (exploratory assumption).
"""
from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import brentq

from coupler import blowing, char_rate
from moving_surface_thermochemistry import Chemistry, REFERENCE_C, TEMPERATURE, sensible
from radial_model import SIGMA, TABLE


@dataclass(frozen=True)
class Face:
    temperature_C: float
    speed_m_s: float
    char_products_kg_m2_s: float
    surface_pyrolysis_gas_kg_m2_s: float
    bulk_pyrolysis_gas_kg_m2_s: float
    h_W_m2_K: float
    convection_W_m2: float
    radiation_W_m2: float
    conduction_into_solid_W_m2: float
    swept_solid_sensible_W_m2: float
    products_sensible_W_m2: float
    pyrolysis_W_m2: float
    char_removal_W_m2: float

    @property
    def energy_residual_W_m2(self):
        return (self.convection_W_m2 + self.radiation_W_m2 + self.swept_solid_sensible_W_m2
                - self.conduction_into_solid_W_m2 - self.products_sensible_W_m2
                - self.pyrolysis_W_m2 - self.char_removal_W_m2)


def solve_face(cell_C, virgin_density, char_density, radius, cell_radius, bulk_gas_flux, cfg):
    """Solve wall temperature, blowing, kinetics, recession and conduction together."""
    if not all(math.isfinite(x) for x in (cell_C, virgin_density, char_density, radius, cell_radius, bulk_gas_flux)):
        raise ValueError('Nonfinite face state')
    if min(virgin_density, char_density, bulk_gas_flux) < 0 or virgin_density + char_density == 0:
        raise ValueError('Invalid face inventory or gas flux')
    if radius <= 0 or cell_radius <= radius:
        raise ValueError('Adjacent cell centre must lie strictly outside the hot-face radius')
    material = Chemistry.from_config(cfg)
    heating, law = cfg['heating'], cfg['char_law']
    if heating['h0_W_m2_K'] <= 0 or law['effective_endothermic_cost_J_kg'] <= 0:
        raise ValueError('Positive film coefficient and endothermic char cost required')

    char_per_volume = char_density + material.char_yield * virgin_density
    alpha = char_density / char_per_volume
    gas_per_volume = (1. - material.char_yield) * virgin_density
    inventory_enthalpy = float(np.dot([virgin_density, char_density], sensible(cell_C)))
    resistance_length = radius * math.log1p((cell_radius-radius) / radius)
    k = (1. - alpha) * TABLE[:, 1] + alpha * TABLE[:, 2]
    k = np.r_[k[0], k]
    integral = np.r_[0., np.cumsum(.5 * (k[1:] + k[:-1]) * np.diff(TEMPERATURE))]
    def primitive(t):
        i = min(np.searchsorted(TEMPERATURE, t, side='right') - 1, len(k)-2)
        delta = t - TEMPERATURE[i]
        return integral[i] + delta * .5 * (k[i] + np.interp(t, TEMPERATURE, k))
    cell_primitive = primitive(cell_C)

    def trial(t):
        char_flux = alpha * char_rate(t, law)
        speed = char_flux / char_per_volume
        gas_flux = gas_per_volume * speed
        film = blowing(heating['h0_W_m2_K'], bulk_gas_flux + gas_flux + char_flux,
                       material.gas_cp_J_kg_K)
        convection = film * (heating['gas_temperature_C'] - t)
        radiation = heating['hot_effective_emissivity'] * SIGMA * (
            (heating['radiative_temperature_C'] + 273.15)**4 - (t + 273.15)**4)
        conduction = (primitive(t) - cell_primitive) / resistance_length
        # Price char removal from char at face temperature. The 35 MJ/kg
        # surrogate supplies the excess cost; no measured product enthalpies
        # are available. Use the char sensible enthalpy as a product proxy.
        product_h = (gas_flux * material.gas_cp_J_kg_K * (t - REFERENCE_C)
                     + char_flux * sensible(t)[1])
        return Face(t, speed, char_flux, gas_flux, bulk_gas_flux, film, convection,
                    radiation, conduction, speed*inventory_enthalpy, product_h,
                    speed*virgin_density*material.pyrolysis_J_per_kg_virgin,
                    char_flux*law['effective_endothermic_cost_J_kg'])

    root = brentq(lambda t: trial(t).energy_residual_W_m2, TEMPERATURE[0], TEMPERATURE[-1], xtol=1e-11)
    return trial(root)

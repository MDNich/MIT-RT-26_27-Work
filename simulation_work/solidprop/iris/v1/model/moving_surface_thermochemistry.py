"""Candidate material-point balance for a conservative moving phenolic surface.

Temperatures are Celsius. Masses, sensible enthalpies and applied energy are
extensive and must refer to the same cell. This module does not move the surface.
"""
from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import brentq

from radial_model import R, TABLE


# The inherited table starts at 22 C. Hold that endpoint cp constant down
# to 0 C to allow a small endothermic cooling increment at initial temperature.
TEMPERATURE = np.r_[0., TABLE[:, 0]]
CP = np.vstack((TABLE[0, 3:5], TABLE[:, 3:5]))
SLOPE = np.diff(CP, axis=0) / np.diff(TEMPERATURE)[:, None]
H_KNOT = np.vstack(([0., 0.], np.cumsum(
    (CP[1:] + CP[:-1]) * np.diff(TEMPERATURE)[:, None] / 2., axis=0)))
REFERENCE_C = float(TABLE[0, 0])
H_KNOT -= H_KNOT[1].copy()


def sensible(temperature_C):
    """Specific sensible enthalpies of virgin and char, J/kg, relative to 22 C."""
    t = np.asarray(temperature_C, dtype=float)
    if np.any(~np.isfinite(t) | (t < TEMPERATURE[0]) | (t > TEMPERATURE[-1])):
        raise ValueError('Temperature outside candidate enthalpy table')
    i = np.minimum(np.searchsorted(TEMPERATURE, t, side='right') - 1, len(SLOPE) - 1)
    d = (t - TEMPERATURE[i])[..., None]
    return H_KNOT[i] + d * (CP[i] + .5 * d * SLOPE[i])


def recover_temperature(virgin, char, enthalpy):
    """Invert the extensive mixture enthalpy exactly within each linear cp span."""
    v, c, h = np.broadcast_arrays(virgin, char, enthalpy)
    if np.any(~np.isfinite(v) | ~np.isfinite(c) | ~np.isfinite(h)
              | (v < 0) | (c < 0) | ((v + c) <= 0)):
        raise ValueError('A finite enthalpy and positive retained mass are required')
    knots = v[..., None] * H_KNOT[:, 0] + c[..., None] * H_KNOT[:, 1]
    if np.any((h < knots[..., 0]) | (h > knots[..., -1])):
        raise ValueError('Retained enthalpy outside candidate table')
    i = np.minimum(np.sum(knots <= h[..., None], axis=-1) - 1, len(SLOPE) - 1)
    dh = h - (v * H_KNOT[i, 0] + c * H_KNOT[i, 1])
    capacity = v * CP[i, 0] + c * CP[i, 1]
    slope = v * SLOPE[i, 0] + c * SLOPE[i, 1]
    return TEMPERATURE[i] + 2. * dh / (capacity + np.sqrt(capacity**2 + 2. * slope * dh))


@dataclass(frozen=True)
class Chemistry:
    char_yield: float
    pyrolysis_J_per_kg_virgin: float
    gas_cp_J_kg_K: float

    @classmethod
    def from_config(cls, cfg):
        material = cfg['material']
        return cls(material['char_reference_density_kg_m3'] / material['virgin_reference_density_kg_m3'],
                   material['pyrolysis_enthalpy_J_kg'], cfg['heating']['gas_cp_J_kg_K'])

    def __post_init__(self):
        if not (0 < self.char_yield < 1 and self.pyrolysis_J_per_kg_virgin > 0
                and self.gas_cp_J_kg_K > 0 and
                all(math.isfinite(x) for x in (self.pyrolysis_J_per_kg_virgin, self.gas_cp_J_kg_K))):
            raise ValueError('Invalid mass yield or thermochemical coefficients')


@dataclass(frozen=True)
class MaterialStep:
    temperature_C: float
    virgin_kg: float
    char_kg: float
    solid_sensible_J: float
    gas_out_kg: float
    reaction_J: float
    gas_sensible_out_J: float


def bulk_step(virgin, char, old_C, dt, applied_J, chemistry):
    """Midpoint Arrhenius update coupled implicitly to the cell energy balance.

    Reaction energy is defined per kg virgin consumed at the common reference.
    Gas leaves with its midpoint sensible enthalpy. Phase sensible enthalpies
    already account for changing inventory and are not added as a second sink.
    A state outside the candidate table raises an error for the caller to handle.
    """
    if not all(math.isfinite(x) for x in (virgin, char, dt, applied_J)):
        raise ValueError('Nonfinite material increment')
    if virgin < 0 or char < 0 or virgin + char <= 0 or dt <= 0:
        raise ValueError('Invalid material inventory or increment')
    old_H = float(np.dot([virgin, char], sensible(old_C)))

    def trial(new_C):
        mid = .5 * (old_C + new_C)
        k = 333. * math.exp(-64081. / (R * (mid + 273.15)))
        lost = virgin * -math.expm1(-k * dt)
        gas = (1. - chemistry.char_yield) * lost
        new_v, new_c = virgin - lost, char + chemistry.char_yield * lost
        new_H = float(np.dot([new_v, new_c], sensible(new_C)))
        return MaterialStep(new_C, new_v, new_c, new_H, gas,
                            lost * chemistry.pyrolysis_J_per_kg_virgin,
                            gas * chemistry.gas_cp_J_kg_K * (mid - REFERENCE_C))

    def residual(new_C):
        s = trial(new_C)
        return s.solid_sensible_J - old_H + s.reaction_J + s.gas_sensible_out_J - applied_J

    new_C = brentq(residual, TEMPERATURE[0], TEMPERATURE[-1], xtol=1e-11)
    return trial(new_C)

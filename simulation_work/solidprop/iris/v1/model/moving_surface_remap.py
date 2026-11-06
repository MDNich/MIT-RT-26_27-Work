"""Conservative radial geometry kernel for a future moving-surface model.

This is NOT a heat-transfer/reaction solver or a recession law. It transports
extensive states under a prescribed boundary movement. Units are per radian
and per metre of axial length; multiply by sector angle and length if needed.
"""
from dataclasses import dataclass
import numpy as np


@dataclass
class Remap:
    density: np.ndarray
    cell_integrals: np.ndarray
    removed_integrals: np.ndarray
    original_integrals: np.ndarray
    balance_residual: np.ndarray


def advance_front(radius, interface, speed, dt):
    """Locate geometric exhaustion for a prescribed constant normal speed.

    The caller must obtain speed from a verified surface mass/energy balance.
    A temperature, conversion threshold or arbitrary cutoff is not used here.
    """
    if not np.all(np.isfinite([radius, interface, speed, dt])):
        raise ValueError('Nonfinite front inputs')
    if radius <= 0 or interface < radius or speed < 0 or dt <= 0:
        raise ValueError('Invalid front inputs')
    if radius == interface:
        return interface, 0., True
    if speed == 0:
        return radius, dt, False
    to_event = (interface - radius) / speed
    if to_event <= dt:
        return interface, to_event, True
    return radius + speed * dt, dt, False


def remap(old_edges, density, new_edges):
    """Integrate piecewise-constant conserved densities over new radial cells.

    The last dimension of density is the old cell index. Other dimensions can
    hold virgin-equivalent mass, char mass, solid enthalpy and related conserved
    quantities. Remap those quantities, not temperature or alpha independently.
    Thermodynamic reconstruction and reaction/removal source terms are the
    caller's responsibility. Interface positions must be retained by the caller
    so heterogeneous material labels are not averaged into one material.

    New cells cover the retained domain [new inner radius, old outer radius].
    A one-entry new_edges array denotes exact exhaustion of this domain. The
    swept-out mass and enthalpy are returned explicitly, not silently deleted.
    """
    old = np.asarray(old_edges, dtype=float)
    new = np.asarray(new_edges, dtype=float)
    field = np.asarray(density, dtype=float)
    if old.ndim != 1 or new.ndim != 1 or len(old) < 2 or len(new) < 1:
        raise ValueError('Expected radial edge arrays')
    if field.ndim < 1 or field.shape[-1] != len(old) - 1:
        raise ValueError('Density field does not match old cells')
    if not all(np.all(np.isfinite(x)) for x in [old, new, field]):
        raise ValueError('Nonfinite remap inputs')
    if old[0] <= 0 or np.any(np.diff(old) <= 0) or np.any(np.diff(new) <= 0):
        raise ValueError('Cells must have strictly positive radial volume')
    if new[0] < old[0] or new[-1] != old[-1]:
        raise ValueError('Only inner recession with a fixed outer boundary is supported')
    # x = r^2/2 is the exact cylindrical volume coordinate per radian/metre.
    xold = old * old / 2
    xnew = new * new / 2
    old_integrals = field * np.diff(xold)
    cumulative = np.concatenate([np.zeros(field.shape[:-1] + (1,)),
                                 np.cumsum(old_integrals, axis=-1)], axis=-1)
    flat = cumulative.reshape((-1, len(old)))
    retained_cumulative = np.array([np.interp(xnew, xold, row) for row in flat])
    retained_cumulative = retained_cumulative.reshape(field.shape[:-1] + (len(new),))
    integrals = np.diff(retained_cumulative, axis=-1)
    removed = retained_cumulative[..., 0]
    original = cumulative[..., -1]
    residual = original - removed - integrals.sum(axis=-1)
    new_density = integrals / np.diff(xnew)
    return Remap(new_density, integrals, removed, original, residual)

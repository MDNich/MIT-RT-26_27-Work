"""Radial finite-volume conduction on the current geometry of the candidate.

Positive face flow is toward increasing radius. All conductances, cell
capacities, source powers and returned flows use one radian and one axial metre.
The caller supplies effective coefficients for the current nonlinear iterate.
"""
import numpy as np
from scipy.linalg import solve_banded


def thermal_geometry(edges, conductivity):
    r = np.asarray(edges, dtype=float)
    k = np.asarray(conductivity, dtype=float)
    if r.ndim != 1 or k.shape != (len(r)-1,) or not len(k):
        raise ValueError('One conductivity per radial cell required')
    if not np.all(np.isfinite(r)) or not np.all(np.isfinite(k)) or min(k) <= 0 or r[0] <= 0 or np.any(np.diff(r)<=0):
        raise ValueError('Invalid radial mesh or conductivity')
    dr = np.diff(r)
    inner, outer = r[:-1], r[1:]
    volumes = .5 * dr * (inner+outer)
    # Radial centroid of a cylindrical shell; offset form avoids subtracting
    # large, nearly equal cubes in the final thin liner cell.
    centres = inner + dr * (inner+2.*outer)/(3.*(inner+outer))
    left = np.log1p((centres-inner)/inner)/k
    right = np.log1p((outer-centres)/centres)/k
    resistances = np.r_[left[0], right[:-1]+left[1:], right[-1]]
    return centres, volumes, 1./resistances


def implicit_step(old_C, capacity, dt, conductance, source, left_C=None, right_C=None):
    """Frozen-coefficient backward Euler. Use source for imposed boundary power.

    An omitted boundary temperature gives zero imposed conductive flow there.
    Source can include an imposed heat flow in the appropriate end cell. A
    supplied boundary temperature instead uses that cell's logarithmic
    half-resistance. Returned flow excludes separately supplied source terms.
    """
    old, cap, g, power = (np.asarray(x, dtype=float) for x in (old_C, capacity, conductance, source))
    n = old.size
    if n == 0 or old.shape != (n,) or cap.shape != old.shape or power.shape != old.shape or g.shape != (n+1,):
        raise ValueError('Inconsistent cell or face arrays')
    if dt <= 0 or not np.isfinite(dt) or np.any(cap<=0) or np.any(g<=0):
        raise ValueError('Positive capacity, step and conductance required')
    if any(not np.all(np.isfinite(x)) for x in (old,cap,g,power)) or any(
            x is not None and not np.isfinite(x) for x in (left_C,right_C)):
        raise ValueError('Nonfinite conduction inputs')
    # Solve for temperature increments, avoiding subtraction of large equal
    # stored enthalpies on an otherwise stationary mesh.
    initial_flow = np.zeros(n+1)
    initial_flow[1:-1] = g[1:-1]*(old[:-1]-old[1:])
    diagonal = cap/dt
    diagonal[:-1] += g[1:-1]
    diagonal[1:] += g[1:-1]
    if left_C is not None:
        initial_flow[0] = g[0]*(left_C-old[0])
        diagonal[0] += g[0]
    if right_C is not None:
        initial_flow[-1] = g[-1]*(old[-1]-right_C)
        diagonal[-1] += g[-1]
    band = np.zeros((3,n))
    band[0,1:] = band[2,:-1] = -g[1:-1]
    band[1] = diagonal
    rhs = power + initial_flow[:-1] - initial_flow[1:]
    delta = rhs/diagonal if n == 1 else solve_banded((1,1),band,rhs)
    new = old+delta
    flow = initial_flow
    flow[1:-1] += g[1:-1]*(delta[:-1]-delta[1:])
    if left_C is not None:
        flow[0] -= g[0]*delta[0]
    if right_C is not None:
        flow[-1] += g[-1]*delta[-1]
    return new, flow

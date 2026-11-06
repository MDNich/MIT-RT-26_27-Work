"""Pure aluminium equilibrium enthalpy surrogate on a single JANAF reference.

The equal-temperature rows of Al-001 give both sides of fusion on the same
reference. All public temperatures are Celsius, specific enthalpies are J/kg
relative to 22 C. The two phase-specific tables have different reference offsets.
"""
import numpy as np

SOURCE = 'https://janaf.nist.gov/tables/Al-001.html'
MOLAR_MASS = 0.0269815385  # kg/mol
MELT_K = 933.45
# K, kJ/mol from NIST-JANAF Al-001, standard state 0.1 MPa.
SOLID_K = np.array([200., 298.15, 300., 400., 500., 600., 700., 800., 900., MELT_K])
SOLID_H = np.array([-2.254, 0., .045, 2.553, 5.186, 7.921, 10.769, 13.749, 16.890, 17.982])
LIQUID_K = np.array([MELT_K, 1000., 1100., 1200., 1300., 1400., 1500., 1600., 1700., 1800.])
LIQUID_H = np.array([28.693, 30.806, 33.981, 37.156, 40.331, 43.506, 46.681, 49.856, 53.031, 56.207])
REFERENCE_H = np.interp(295.15, SOLID_K, SOLID_H)
TO_SPECIFIC = 1000. / MOLAR_MASS
FUSION = (LIQUID_H[0] - SOLID_H[-1]) * TO_SPECIFIC


def equilibrium(specific_h):
    """Recover temperature and liquid mass fraction, including isothermal coexistence."""
    h = np.asarray(specific_h, dtype=float)/TO_SPECIFIC + REFERENCE_H
    if np.any(~np.isfinite(h)) or np.any((h < SOLID_H[0]) | (h > LIQUID_H[-1])):
        raise ValueError('Enthalpy outside the adopted pure Al data')
    t = np.where(h < SOLID_H[-1], np.interp(h, SOLID_H, SOLID_K),
                 np.interp(h, LIQUID_H, LIQUID_K))
    fraction = np.clip((h-SOLID_H[-1])/(LIQUID_H[0]-SOLID_H[-1]), 0., 1.)
    return t-273.15, fraction


def caloric(temperature_C, width_K):
    """Regularized specific h and its consistent slope for a temperature solver.

    Connect the two sensible-heat branches across a narrow interval centred at
    the pure-metal melting point. Width is a numerical refinement parameter.
    """
    if not 0. < width_K < 2.*min(MELT_K-SOLID_K[-2],LIQUID_K[1]-MELT_K):
        raise ValueError('Melting interval must fit between the adjacent tabulated points')
    t = np.asarray(temperature_C, dtype=float)+273.15
    if np.any(~np.isfinite(t)) or np.any((t < SOLID_K[0]) | (t > LIQUID_K[-1])):
        raise ValueError('Temperature outside the adopted pure Al data')
    lo, hi = MELT_K-width_K/2., MELT_K+width_K/2.
    knots = np.r_[SOLID_K[:-1],lo,hi,LIQUID_K[1:]]
    h = np.r_[SOLID_H[:-1],np.interp(lo,SOLID_K,SOLID_H),
              np.interp(hi,LIQUID_K,LIQUID_H),LIQUID_H[1:]]
    index = np.clip(np.searchsorted(knots,t,side='right')-1,0,len(knots)-2)
    return (np.interp(t,knots,h)-REFERENCE_H)*TO_SPECIFIC, np.diff(h)[index]/np.diff(knots)[index]*TO_SPECIFIC

"""Check the standalone high-temperature Al surrogate before coupling to the wall."""
from pathlib import Path
import numpy as np
from aluminium_phase_enthalpy import caloric, equilibrium, FUSION, MELT_K, MOLAR_MASS, SOURCE
from continuous_heating_campaign import digest
from ops import ROOT, atomic, disks, utc


def main():
    disks()
    # One independent knot difference below fusion, across fusion and above fusion.
    h400, _ = caloric(400.-273.15,2.)
    h1200, _ = caloric(1200.-273.15,2.)
    assert abs((h1200-h400)*MOLAR_MASS/1000. - (37.156-2.553)) < 1e-12
    assert abs(FUSION*MOLAR_MASS/1000.-10.711) < 1e-12
    assert caloric(22.,1.)[0] == 0.
    solid_melt_h = h400+(17.982-2.553)*1000./MOLAR_MASS
    f = np.linspace(0.,1.,11)
    temp, fraction = equilibrium(solid_melt_h+f*FUSION)
    assert max(abs(temp-(MELT_K-273.15))) < 1e-9 and max(abs(fraction-f)) < 1e-12
    checks = []
    for width in (4.,2.,1.,.5):
        t = np.linspace(22.,1400.,2001)
        h, cp = caloric(t,width)
        assert np.all(cp>0) and np.all(np.diff(h)>0)
        eq, _ = equilibrium(h)
        error = float(max(abs(eq-t)))
        assert error <= width/2.+1e-9
        tmid = MELT_K-273.15
        half = width/2.
        low, _ = caloric(tmid-half,width)
        high, _ = caloric(tmid+half,width)
        _, apparent = caloric(tmid,width)
        assert abs((high-low)-apparent*width) < 1e-6
        checks.append(dict(smoothing_width_K=width,maximum_temperature_departure_K=error,
                           integrated_transition_J_kg=float(high-low)))
    atomic(ROOT/'validation/pure_al_phase_enthalpy.json',dict(passed=True,utc=utc(),source=SOURCE,
        molar_mass_kg_mol=MOLAR_MASS,melting_K=MELT_K,fusion_J_per_kg=FUSION,
        module_sha256=digest(ROOT/'model/aluminium_phase_enthalpy.py'),check_sha256=digest(Path(__file__)),
        checks=checks,qualification='Equilibrium pure Al caloric data and numerical transitions only. '
        'No alloy, transport, casing strength, geometry or coupled liner result.'))
    print(f'Fusion {FUSION/1000:.2f} kJ/kg; isothermal mixture and four interval checks pass')


if __name__ == '__main__':
    main()

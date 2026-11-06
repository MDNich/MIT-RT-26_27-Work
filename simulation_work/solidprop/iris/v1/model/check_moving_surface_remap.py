"""Analytic conservation/event checks for the candidate geometry kernel only."""
import hashlib
import json
import math
import numpy as np
from moving_surface_remap import advance_front, remap
from ops import ROOT, atomic, disks, utc


def main():
    disks()
    # Unequal-volume cells with an exact independently specified integral.
    old = np.sqrt([2., 4., 8.])  # volume coordinates 1, 2, 4
    new = np.sqrt([3., 5., 8.])  # 1.5, 2.5, 4
    d = remap(old, np.array([[2., 5.], [10., 30.]]), new)
    assert np.allclose(d.cell_integrals, [[3.5, 7.5], [20., 45.]], rtol=0, atol=1e-13)
    assert np.allclose(d.removed_integrals, [1., 5.], rtol=0, atol=1e-13)
    assert np.max(np.abs(d.balance_residual)) < 1e-13

    # Zero motion preserves fields exactly, including their internal energy.
    identity = remap(old, np.array([[2., 5.], [10., 30.]]), old)
    assert np.allclose(identity.density, [[2., 5.], [10., 30.]], rtol=0, atol=1e-13)
    assert np.max(np.abs(identity.removed_integrals)) == 0
    assert advance_front(.04, .045, 0., 10.) == (.04, 10., False)

    # Pure-char, prescribed-flux analytic motion: ds/dt = flux/rho.
    # These values are manufactured test inputs, not the motor erosion law.
    cases = []
    for cells, dt in [(20, .7), (80, .13), (160, .031)]:
        r0, outer, rho, flux, cp, temperature = .04, .045, 600., .03, 1500., 1000.
        exact_time = (outer-r0)*rho/flux
        edges = np.linspace(r0, outer, cells+1)
        field = np.vstack([np.full(cells, rho), np.full(cells, rho*cp*temperature)])
        original = np.array([rho, rho*cp*temperature])*(outer**2-r0**2)/2
        removed = np.zeros(2)
        t = 0.
        while True:
            front, used, done = advance_front(float(edges[0]), outer, flux/rho, dt)
            new_edges = np.array([outer]) if done else np.linspace(front, outer, cells+1)
            transfer = remap(edges, field, new_edges)
            removed += transfer.removed_integrals
            field, edges = transfer.density, new_edges
            t += used
            assert np.max(np.abs(transfer.balance_residual)/np.maximum(abs(original), 1.)) < 1e-12
            if done:
                break
        relative = float(np.max(np.abs(removed-original)/original))
        assert abs(t-exact_time) < 1e-8 and relative < 1e-11
        assert field.shape[-1] == 0  # no retained heat capacity after exhaustion
        cases.append(dict(cells=cells,dt_s=dt,prescribed_exhaustion_s=t,
                          analytic_exhaustion_s=exact_time,mass_enthalpy_relative_error=relative))
    source = ROOT/'model/moving_surface_remap.py'
    out = dict(checked_utc=utc(),passed=True,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        checks=['Exact nonuniform cylindrical overlap integrals', 'Identity and zero-motion limits',
                'Mass and enthalpy carried out with swept volume', 'Analytic prescribed-flux pure-char front',
                'Exact geometric final event with no residual thermal capacity'],cases=cases,
        qualification='Manufactured tests of a geometry/remapping kernel only. '
        'No coupled reaction/thermal solver, physical recession law, native implementation or motor lifetime is established.')
    atomic(ROOT/'validation/moving_surface_remap_verification.json',out)
    print(json.dumps(out,indent=2))


if __name__=='__main__':
    main()

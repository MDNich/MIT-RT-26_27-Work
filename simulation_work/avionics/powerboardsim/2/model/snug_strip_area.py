"""Localize bilinear strip strains by physical mid-surface area and proximity to the cell attachment."""
import argparse
from pathlib import Path

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read
from damage_footprint import shell_components
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_bilinear_strain import fields
from snug_local_checkpoint import CAMPAIGN
from stage_snug_fit import AUDIT


def surfaces(raw, mesh):
    els = np.array(mesh['elements'])
    element_ids = 1 + np.arange(len(els))
    order = np.argsort(raw.mesh.enum)
    indx = order[positions(raw.mesh.enum[order], element_ids)]
    native = raw.mesh.elem
    assert np.array_equal(els, [native[k][10:14] for k in indx])
    ids, inv = np.unique(els, return_inverse=True)
    points = raw.mesh.nodes[positions(raw.mesh.nnum, ids)]
    assert np.allclose(points, [mesh['nodes'][str(n)] for n in ids], rtol=0, atol=1e-7)
    compact = inv.reshape(els.shape)
    x = points[compact]
    def split_area(v):
        first = np.cross(v[:, 1]-v[:, 0], v[:, 2]-v[:, 0])
        second = np.cross(v[:, 2]-v[:, 0], v[:, 3]-v[:, 0])
        return .5*(np.linalg.norm(first, axis=1) + np.linalg.norm(second, axis=1))
    area = split_area(x)
    assert np.allclose(area, split_area(np.roll(x, 1, axis=1)), rtol=1e-5, atol=1e-8)
    assert area.min() > 0 and np.isclose(area.sum(), mesh['area'], rtol=1e-6)
    count, label = shell_components(compact, len(ids))
    assert count == 2 and np.all(label[compact] == label[compact[:, :1]])
    centres = x.mean(1)
    strip = label[compact[:, 0]]
    high_y = max(range(count), key=lambda i: centres[strip == i, 1].mean())
    return els, centres, area, strip == high_y


def measure(raw, mesh, geometry, detail):
    els, centres, area, high_y = geometry
    values = fields(raw, detail['native_set']-1, mesh)
    i, side = np.unravel_index(values.argmax(), values.shape)
    assert abs(values[i, side]-detail['peak']) < 1.e-9
    if detail['peak'] > 0:
        assert detail['element'] == int(i+1) and detail['face'] == ('bottom', 'top')[side]
    regions = np.array(mesh['region'])
    bands = {}
    for percentage in (1, 5, 10):
        hits = values.max(1) >= percentage/100.
        bands[str(percentage)] = dict(elements=int(hits.sum()), area_mm2=float(area[hits].sum()),
            low_Y_area_mm2=float(area[hits & ~high_y].sum()), high_Y_area_mm2=float(area[hits & high_y].sum()),
            regions={name:float(area[hits & (regions == name)].sum()) for name in sorted(set(regions[hits]))})
    peak = None
    if detail['peak'] > 0:
        peak = dict(element=int(i+1), face=detail['face'], region=str(regions[i]),
                    strip='high Y' if high_y[i] else 'low Y', centre_xyz_mm=centres[i].tolist(),
                    nodes_tied_to_cell=int(np.isin(els[i], mesh['attachment']).sum()),
                    nodes_on_clamp_annulus=int(np.isin(els[i], mesh['clamp']).sum()))
    return dict(native_set=detail['native_set'], peak_equivalent_plastic_strain=detail['peak'], location=peak,
                shell_area_mm2=float(area.sum()), bands_by_percent=bands)


def run(folder):
    case = read(folder/'capture.json')['case']
    cp = AUDIT/f'{case}_{folder.name}_checkpoint.json'
    rec = read(cp)
    src = AUDIT/f'{case}_{folder.name}_nickel_strain.json'
    strains = read(src)
    assert strains['checkpoint_sha256'] == digest(cp)
    source = 'lateral_friction_locked'
    mesh_file = ROOT/'.runtime/local_inputs'/source/'mesh.json'
    mesh_sha = read(ROOT/'validation/local_inputs.json')[source]['files']['mesh.json']
    verified(mesh_file, mesh_sha)
    mesh = read(mesh_file)
    ref = ROOT/'.runtime/archive'/CAMPAIGN/rec['bare_case']/'pull.rst'
    verified(ref, rec['bare_rst_sha256'])
    verified(folder/'pull.rst', rec['rst_sha256'])
    basic = reader.read_binary(ref)
    snug = reader.read_binary(folder/'pull.rst')
    geometry = surfaces(snug, mesh)
    for a, b in zip(geometry, surfaces(basic, mesh), strict=True):
        assert np.allclose(a, b, atol=1e-8, rtol=0)
    comp = strains['comparison']
    case_state = comp['shared_travel_cased']
    assert rec['states'][case_state['native_set']-1]['within_screens']
    stations = dict(snug=measure(snug, mesh, geometry, case_state),
                    bare_bracket=[measure(basic, mesh, geometry, r) for r in comp['shared_travel_bare_bracket']])
    write_json(AUDIT/f'{case}_{folder.name}_strip_area.json', dict(case=case, checkpoint_sha256=digest(cp),
               strain_sha256=digest(src), mesh_sha256=mesh_sha, supported_travel_mm=comp['shared_travel_mm'],
               bare_bracket_travel_mm=rec['last_common_travel']['bare']['native_travel_mm'], stations=stations,
               scope='Undeformed shell mid-surface area counted once when the mean equivalent plastic strain on either '
                     'exterior face reaches the selected level. These reporting levels describe strain distribution.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    run(parser.parse_args().folder)

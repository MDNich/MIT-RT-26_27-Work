"""Measure vertical separation between the deformed tab and PCB contact faces (mm)."""
import argparse
from itertools import combinations

import numpy as np
import shapely

from audit_local import ROOT, read, table
from film_identity import digest, verified, write_json
from native_rst import read_rst


def patch_volumes(rst, inventory, material, contact_type, z_mm):
    """Recover each listed native face from three corner IDs and its parent solid."""
    grid = rst.quadgrid
    domain = grid.extract_cells((grid.cell_data['ansys_material_type'] == material)
                                & np.isin(grid.cell_data['ansys_elem_type_num'], [185, 186, 187]))
    rows = inventory[inventory['type'] == contact_type]
    expected = {tuple(sorted(int(r[f'node{k}']) for k in (1, 2, 3))): int(r['pair']) for r in rows}
    assert len(expected) == len(rows)
    skin = domain.extract_surface(algorithm='dataset_surface', nonlinear_subdivision=0)
    ids = skin.point_data['ansys_node_num']
    faces = skin.faces
    parent = {pair: [] for pair in range(880, 884)}
    offset = 0
    for j, element in enumerate(skin.cell_data['ansys_elem_num']):
        count = faces[offset]
        vertices = faces[offset + 1:offset + 1 + count]
        offset += count + 1
        if np.max(abs(skin.points[vertices, 2] * 1000 - z_mm)) > .00001:
            continue
        hits = [key for key in combinations(sorted(ids[vertices]), 3) if key in expected]
        if hits:
            assert len(hits) == 1
            parent[expected.pop(hits[0])].append(element)
    if expected:
        raise ValueError(f'{len(expected)} listed native tab/PCB faces could not be matched')
    return {pair: domain.extract_cells(np.isin(domain.cell_data['ansys_elem_num'], elements))
            for pair, elements in parent.items()}


def triangles(domain, rst, z_mm, subdivisions, field):
    cells = domain.copy()
    ids = cells.point_data['ansys_node_num']
    index = np.searchsorted(rst.mesh.nnum, ids)
    assert np.array_equal(rst.mesh.nnum[index], ids)
    xyz = rst.mesh.nodes[index] * 1000
    cells.point_data['initial_z_mm'] = xyz[:, 2]
    if field is not None:
        node_ids, displacement = field
        idx = np.searchsorted(node_ids, ids)
        assert np.array_equal(node_ids[idx], ids)
        xyz = xyz + displacement[idx, :3] * 1000
    cells.points = xyz
    cells.point_data['deformed_mm'] = xyz
    skin = cells.extract_surface(algorithm='dataset_surface', nonlinear_subdivision=subdivisions).triangulate()
    faces = skin.regular_faces
    keep = np.max(abs(skin.point_data['initial_z_mm'][faces] - z_mm), axis=1) < .00001
    # VTK may store the rendered surface vertices as float32. The interpolated
    # coordinate field retains the precision of the parent solid nodes.
    smooth_xyz = skin.point_data['deformed_mm']
    assert np.max(abs(skin.points - smooth_xyz)) < .00002
    facets = smooth_xyz[faces[keep]]
    assert len(facets)
    return facets


def area_below_gap(xy, gap, starts, area, minima, maxima, limit):
    """Clip each convex overlap polygon at its affine gap contour and sum projected areas."""
    total = float(area[maxima <= limit].sum())
    ends = np.r_[starts[1:], len(xy)]
    for i in np.flatnonzero((minima < limit) & (maxima > limit)):
        a,b = starts[i],ends[i]
        points = xy[a:b]
        height = gap[a:b] - limit
        assert np.array_equal(points[0], points[-1])
        clipped = []
        for j in range(len(points)-1):
            first, last = height[j], height[j+1]
            if first <= 0:
                clipped.append(points[j])
            if (first < 0 < last) or (last < 0 < first):
                clipped.append(points[j] + first/(first-last)*(points[j+1]-points[j]))
        if len(clipped) >= 3:
            q = np.array(clipped) - clipped[0]
            total += .5*abs(np.sum(q[:-1,0]*q[1:,1] - q[1:,0]*q[:-1,1]))
    assert -1e-10 <= total <= float(area.sum())+1e-8
    return total


def overlap_vertices(tab, pcb):
    """Intersect projected triangles and evaluate both affine heights at every overlap vertex."""
    tab_polys = shapely.polygons(tab[:, :, :2])
    pcb_polys = shapely.polygons(pcb[:, :, :2])
    for polygons in (tab_polys, pcb_polys):
        assert np.all(shapely.is_valid(polygons))
        # A folded footprint would assign two different heights at the same XY.
        area = shapely.area(polygons).sum()
        if not np.isclose(shapely.area(shapely.union_all(polygons)), area, rtol=1e-8, atol=1e-8):
            raise ValueError('Deformed face folds over itself in board-Z projection')
    tab_ids, pcb_ids = shapely.STRtree(pcb_polys).query(tab_polys, predicate='intersects')
    pieces = shapely.intersection(tab_polys[tab_ids], pcb_polys[pcb_ids])
    usable = shapely.area(pieces) > 1e-12
    tab_ids, pcb_ids, pieces = tab_ids[usable], pcb_ids[usable], pieces[usable]
    area = shapely.area(pieces)
    assert len(area) and np.all(shapely.get_type_id(pieces) == 3)
    xy, index = shapely.get_coordinates(pieces, return_index=True)

    def heights(tris, members):
        origin = tris[:, 0, :]
        edges = tris[:, 1:, :] - origin[:, None, :]
        gradient = np.linalg.solve(edges[:, :, :2], edges[:, :, 2:])[:, :, 0]
        targets = members[index]
        return origin[targets, 2] + np.einsum('ij,ij->i', gradient[targets], xy - origin[targets, :2])

    gap = heights(pcb, pcb_ids) - heights(tab, tab_ids)
    assert np.all(np.isfinite(gap))
    # Affine separation reaches its extrema at the vertices of each convex overlap.
    starts = np.flatnonzero(np.r_[True, np.diff(index) != 0])
    assert len(starts) == len(area)
    return xy, gap, starts, area


def gap_on_overlap(tab, pcb, *, seating_area=False):
    xy, gap, starts, area = overlap_vertices(tab,pcb)
    minima, maxima = np.minimum.reduceat(gap, starts), np.maximum.reduceat(gap, starts)
    row = dict(projected_overlap_mm2=float(sum(area)), minimum_gap_mm=float(min(gap)), maximum_gap_mm=float(max(gap)),
                area_over_10um_crossing_lower_mm2=float(sum(area[maxima < -.010])),
                area_over_10um_crossing_upper_mm2=float(sum(area[minima < -.010])))
    if seating_area:
        row['area_gap_le_50um_mm2'] = area_below_gap(xy,gap,starts,area,minima,maxima,.050)
        row['area_gap_le_zero_mm2'] = area_below_gap(xy,gap,starts,area,minima,maxima,0.)
    return row


def plane_controls():
    tri = np.array([[[0., 0., 0.], [2., 0., 0.], [0., 2., 0.]]])
    pcb = tri + [0., 0., 3.]
    for travel, offset in [(0., 0.), (2., 5.), (3.02, -8.)]:
        rec = gap_on_overlap(tri + [0, 0, travel + offset], pcb + [0, 0, offset])
        assert np.isclose(rec['projected_overlap_mm2'], 2.)
        assert np.allclose([rec['minimum_gap_mm'], rec['maximum_gap_mm']], 3. - travel)
        assert rec['area_over_10um_crossing_lower_mm2'] == (2. if travel > 3.01 else 0.)
    incline = tri + [1., 0., 2.]
    wedge=tri.copy()
    wedge[:,:,2]=tri[:,:,0]
    clipped=gap_on_overlap(tri,wedge,seating_area=True)
    assert np.isclose(clipped['area_gap_le_50um_mm2'],2*.05-.05**2/2,rtol=0,atol=1e-10)
    assert clipped['area_gap_le_zero_mm2']==0.
    assert gap_on_overlap(tri,tri,seating_area=True)['area_gap_le_zero_mm2']==2.
    incline[0, 1, 2] += 4.
    rec = gap_on_overlap(incline, pcb)
    assert np.allclose([rec['projected_overlap_mm2'], rec['minimum_gap_mm'], rec['maximum_gap_mm']], [.5, -1., 1.])


def run(case, campaign, requested):
    plane_controls()
    proof_file = ROOT / 'validation/global' / f'{case}.json'
    if not proof_file.is_file():
        proof_file = ROOT / 'validation/review_global' / f'{case}.json'
    proof = read(proof_file)
    assert proof['case'] == case and proof['campaign'] == campaign
    path = ROOT / '.runtime/archive' / campaign / case / 'file.rst'
    verified(path, proof['rst_sha256'])
    rst = read_rst(path)
    times = rst.time_values
    indices = np.flatnonzero(rst._resultheader['ls_table'][:, 1] != 999999)
    sets = requested or [int(indices[-1]) + 1]
    assert all(i - 1 in indices for i in sets)
    pre = ROOT / '.runtime/board_surface_initial_v1'
    initial = read(ROOT / 'validation/board_surface_initial.json')
    verified(pre / 'pre.out', initial['listing_sha256'])
    verified(pre / 'pre.inp', initial['input_sha256'])
    facefile = pre / 'seat_faces.csv'
    verified(facefile, initial['faces_sha256'])
    inventory = table(facefile)
    for p in range(880, 884):
        for typ, side in [(857, 'PCB'), (858, 'PLA')]:
            assert np.sum((inventory['pair'] == p) & (inventory['type'] == typ)) == initial['pairs'][str(p)][side+'_facets']
    domains = [patch_volumes(rst, inventory, mat, typ, z) for mat, typ, z in
               [(850, 858, -3.55118), (208, 857, -.55118)]]
    measurements = {}
    for k in [0, *sets]:
        field = None if k == 0 else rst.nodal_displacement(k - 1)
        if field is not None:
            assert np.all(np.diff(field[0]) > 0)
        levels = {}
        for ndiv in (1, 2):
            feet = {}
            for p in range(880, 884):
                facets = [triangles(v[p], rst, z, ndiv, field) for v, z in zip(domains, (-3.55118, -.55118), strict=True)]
                feet[p] = gap_on_overlap(*facets, seating_area=True)
                if k == 0:
                    assert np.allclose([feet[p]['minimum_gap_mm'], feet[p]['maximum_gap_mm']], 3., rtol=0., atol=2e-6), (p, ndiv, feet[p])
            levels[ndiv] = feet
        measurements[k] = dict(time=None if k == 0 else float(times[k-1]), subdivisions=levels)
    output = ROOT / 'validation/tab_gap' / f'{case}-sets-{"-".join(map(str, sets))}.json'
    write_json(output, dict(case=case, campaign=campaign, rst_sha256=proof['rst_sha256'],
               native_face_inventory_sha256=digest(facefile), native_preflight_sha256=initial['input_sha256'],
               measurements=measurements, scope='Board-Z gap between overlapping projections of the two native face '
               'patches at each foot. Empty board holes and tab overhangs carry no overlap area. Negative separation '
               'denotes a geometric crossing. Result zero is the as-meshed assembly. No contact law is inferred.'))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case')
    parser.add_argument('campaign')
    parser.add_argument('sets', nargs='*', type=int)
    args = parser.parse_args()
    print(run(args.case, args.campaign, args.sets))

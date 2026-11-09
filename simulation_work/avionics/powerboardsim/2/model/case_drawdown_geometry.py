"""Bracket first contact during rigid vertical assembly of the supplied STEP solids."""
import math
import sys
from functools import lru_cache

import gmsh
import numpy as np
from scipy.optimize import linear_sum_assignment

from audit_local import ROOT, read
from case_fit import case as case_step, old as hardware_step, PCB_CENTER, PCB_BOTTOM
from extend_board import FACE_MATERIALS
from film_identity import digest, verified, write_json
from native_rst import read_rst


def first_touch(distance, stroke=3., tolerance=1e-6, resolution=.00025):
    """Bracket the earliest possible touch and the first sampled near-zero gap.

    Rigid translation bounds gap change by the distance moved. An interval whose
    two endpoint distance cones intersect above tolerance is clear throughout.
    """
    earliest = None

    def scan(lo, hi, left, right):
        nonlocal earliest
        width = hi - lo
        if abs(left - right) > width + 1e-6:
            raise ValueError('Distance inconsistent with rigid translation')
        if (left + right - width) / 2 > tolerance:
            return None
        if width <= resolution:
            if earliest is None:
                earliest = lo
            if left <= tolerance:
                return lo
            if right <= tolerance:
                return hi
            return None
        mid = (lo + hi) / 2
        midpoint_gap = distance(mid)
        found = scan(lo, mid, left, midpoint_gap)
        if found is None:
            found = scan(mid, hi, midpoint_gap, right)
        return found

    found = scan(0., stroke, distance(0.), distance(stroke))
    if earliest is not None and found is None:
        raise ValueError('Unresolved near-touch interval')
    return None if found is None else [earliest, found]


def match_bodies(occ, original, grid):
    materials = np.arange(173, 208)
    solid = np.isin(grid.cell_data['ansys_elem_type_num'], [185, 186, 187])
    mesh_boxes = []
    for material in materials:
        selection = solid & (grid.cell_data['ansys_material_type'] == material)
        points = grid.extract_cells(selection).points * 1000
        mesh_boxes.append(np.r_[points.min(axis=0), points.max(axis=0)])
    boxes = np.array([occ.getBoundingBox(*body) for body in original])
    metric = np.max(abs(boxes[:, None, :] - np.asarray(mesh_boxes)[None, :, :]), axis=2)
    ii, jj = linear_sum_assignment(metric)
    assert len(ii) == len(original) == len(materials) == 35
    assert np.array_equal(metric.argmin(axis=1), jj)
    assert max(metric[ii, jj]) < .5
    assert min(np.sort(metric, axis=1)[:, 1] - metric[ii, jj]) > 1.
    return [(original[i], int(materials[j])) for i, j in zip(ii, jj, strict=True)]


def run(campaign):
    base = read(ROOT / 'validation/global/bare_static.json')
    assert base['campaign'] == campaign
    path = ROOT / '.runtime/archive' / campaign / 'bare_static/file.rst'
    verified(path, base['rst_sha256'])
    original_fit = read(ROOT / 'validation/case_fit.json')[0]
    assert original_fit['tab_standoff_mm'] == 0
    endpoint = {r['body']: r['overlap_mm3'] for r in original_fit['overlaps']}
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        occ = gmsh.model.occ
        hardware = occ.importShapes(str(hardware_step))
        cap, = occ.importShapes(str(case_step))
        occ.rotate([cap], 0, 0, 0, 1, 0, 0, -math.pi / 2)
        occ.translate([cap], *PCB_CENTER, PCB_BOTTOM - 13.)
        position = 0.
        results = []

        def move(travel):
            nonlocal position
            occ.translate([cap], 0, 0, travel - position)
            position = travel

        for body, material in match_bodies(occ, hardware, read_rst(path).quadgrid):
            @lru_cache(None)
            def gap(travel):
                move(travel)
                return float(occ.getDistance(*cap, *body)[0])

            bracket = first_touch(gap)
            tag = body[1]
            record = dict(STEP_body=tag, native_material=material, native_contact_target=material in FACE_MATERIALS,
                          gap_at_3mm_standoff_mm=gap(0.), first_touch_travel_bracket_mm=bracket,
                          exact_flush_overlap_mm3=endpoint.get(tag, 0.), STEP_centre_mm=list(occ.getCenterOfMass(*body)))
            if bracket is not None:
                assert material in FACE_MATERIALS and bracket[1] - bracket[0] < .005
                after = min(bracket[1] + .05, 3.)
                move(after)
                shapes, _ = occ.intersect([cap], [body], removeObject=False, removeTool=False)
                volume = sum(occ.getMass(d, t) for d, t in shapes if d == 3)
                assert volume > 1e-5 and not any(s == cap or s in hardware for s in shapes)
                occ.remove(shapes, recursive=True)
                record.update(boolean_check_travel_mm=after, boolean_overlap_mm3=volume)
            if tag in endpoint:
                assert bracket is not None
            results.append(record)
    finally:
        gmsh.finalize()
    write_json(ROOT / 'validation/rigid_case_drawdown.json', dict(
        case_STEP_sha256=digest(case_step), hardware_STEP_sha256=digest(hardware_step),
        original_board_RST_sha256=base['rst_sha256'], native_target_materials=FACE_MATERIALS,
        stroke_mm=3., touch_distance_tolerance_mm=1e-6, records=results,
        scope='Undeformed STEP solids at fixed registration. The case translates vertically from the 3 mm stand-off. '
              'No applied force, bolt tightening or deformation. The interval bounds use that distance can close '
              'by at most the imposed travel.'))


if __name__ == '__main__':
    run(sys.argv[1])

"""Compare the default native case exports with the archived board and the as-supplied Balius STEP."""
from functools import lru_cache
from itertools import combinations, permutations
import hashlib
import json
import math

import gmsh
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from case_drawdown_geometry import first_touch
from case_fit import ROOT, PCB_BOTTOM, PCB_CENTER, case, old

CANDIDATES = ROOT / 'geometry/candidates'
ZPHR = CANDIDATES / 'zphr-av-fcpbcase.STEP'
BALIUS = CANDIDATES / 'Balius-native-verification.STEP'
CELLS = [4, 19, 15]
WASHERS = [6, 9, 10, 11]


def cylinders(path):
    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone and reader.TransferRoots()
    faces = TopExp_Explorer(reader.OneShape(), TopAbs_FACE)
    surfaces = []
    while faces.More():
        surface = BRepAdaptor_Surface(TopoDS.Face(faces.Current()))
        faces.Next()
        if surface.GetType() == GeomAbs_Cylinder:
            cyl = surface.Cylinder()
            axis = cyl.Axis()
            surfaces.append((cyl.Radius(), axis.Direction().Coord(), axis.Location().Coord()))
    return surfaces


def case_mounts(path, radius, tolerance):
    return sorted({(round(p[0], 6), round(p[2], 6)) for r, d, p in cylinders(path)
                   if abs(abs(d[1]) - 1) < 1e-8 and abs(r - radius) < tolerance})


def mount_error_bound(holes):
    # A pair-distance error of e needs at least one endpoint to move by e/2.
    # All ordered assignments cover the two board orientations, translations and rotations.
    holes = np.asarray(holes)
    board = np.array([(x, y) for x in (-62.865/2, 62.865/2) for y in (-114.427/2, 114.427/2)])
    pairs = np.array(list(combinations(range(4), 2)))
    target = np.linalg.norm(board[pairs[:, 0]] - board[pairs[:, 1]], axis=1)
    orders = np.array(list(permutations(range(len(holes)), 4)))
    selected = holes[orders]
    lengths = np.linalg.norm(selected[:, pairs[:, 0]] - selected[:, pairs[:, 1]], axis=2)
    return float(np.abs(lengths - target).max(axis=1).min() / 2)


def installed_balius(path, measure_onset):
    gmsh.model.add(path.stem)
    occ = gmsh.model.occ
    hardware = occ.importShapes(str(old))
    cap, = occ.importShapes(str(path))
    orig_volume = occ.getMass(*cap)
    occ.rotate([cap], 0, 0, 0, 1, 0, 0, -math.pi/2)
    occ.translate([cap], *PCB_CENTER, PCB_BOTTOM - 13)
    travel_now = 0.
    def position(travel):
        nonlocal travel_now
        occ.translate([cap], 0, 0, travel-travel_now)
        travel_now = travel

    gaps = {}
    for stand in (3., 2.5, 1.25):
        position(3-stand)
        gaps[str(stand)] = {str(t): occ.getDistance(*cap, 3, t)[0] for t in CELLS + WASHERS}
    records = []
    if measure_onset:
        for body in hardware:
            @lru_cache(None)
            def gap(travel):
                position(travel)
                return occ.getDistance(*cap, *body)[0]
            bracket = first_touch(gap)
            if bracket:
                position(min(3., bracket[1] + .05))
                solid, _ = occ.intersect([cap], [body], removeObject=False, removeTool=False)
                volume = sum(occ.getMass(*s) for s in solid if s[0] == 3)
                assert volume > 1e-6 and not any(s in hardware or s == cap for s in solid)
                occ.remove(solid, recursive=True)
                records.append(dict(step_body=body[1], stand_off_at_first_touch_mm=[3-bracket[1], 3-bracket[0]],
                                    confirmation_overlap_mm3=volume))
    gmsh.model.remove()
    return dict(volume_mm3=orig_volume, shortest_gaps_mm=gaps, onsets=records)


def run():
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.model.add('candidate')
        occ = gmsh.model.occ
        solid, = occ.importShapes(str(ZPHR))
        assert solid[0] == 3
        span = occ.getBoundingBox(*solid)
        bores = case_mounts(ZPHR, 1.7, .001)
        assert len(bores) == 14
        pocket_z = sorted({round(p[2], 8) for r, d, p in cylinders(ZPHR)
                           if abs(abs(d[0])-1)<1e-8 and abs(r-11.)<1e-6})
        assert len(pocket_z) == 6 and np.ptp(np.diff(pocket_z)) < 1e-5
        candidate = dict(extents_xyz_mm=[span[i+3]-span[i] for i in range(3)], volume_mm3=occ.getMass(*solid),
                         mounting_hole_xz_mm=bores, mounting_bore_diameter_mm=3.4,
                         min_possible_worst_hole_offset_lower_bound_mm=mount_error_bound(bores),
                         nominal_M3_combined_radial_float_mm=(4.2-3)/2+(3.4-3)/2,
                         cradle_radius_mm=11., cradle_axis_z_mm=pocket_z, cradle_pitch_mm=float(np.mean(np.diff(pocket_z))))
        gmsh.model.remove()
        gmsh.model.add('Balius boolean')
        first, = occ.importShapes(str(case))
        second, = occ.importShapes(str(BALIUS))
        difference = {}
        for key, a, b in [('supplied_only_mm3', first, second), ('native_only_mm3', second, first)]:
            result, _ = occ.cut([a], [b], removeObject=False, removeTool=False)
            difference[key] = sum(occ.getMass(*s) for s in result if s[0] == 3)
            assert not any(s in [first,second] for s in result)
            occ.remove(result, recursive=True)
        gmsh.model.remove()
        baseline = installed_balius(case, False)
        new = installed_balius(BALIUS, True)
    finally:
        gmsh.finalize()
    paths = [case, case.with_suffix('.SLDPRT'), old, ZPHR, ZPHR.with_suffix('.SLDPRT'), BALIUS]
    return dict(sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                solidworks_export=dict(version='2026 SP4.1', configuration='Default', schema='AP203',
                                       save_errors=0, save_warnings=0),
                Zphr=candidate, Balius_difference=difference, Balius_supplied=baseline, Balius_native=new)


if __name__ == '__main__':
    summary = run()
    (ROOT/'validation/alternate_case_fit.json').write_text(json.dumps(summary, indent=2)+'\n')

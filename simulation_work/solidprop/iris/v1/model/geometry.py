"""Exact two-volume STEP sectors and independent round-trip dimension checks."""
import argparse
import json
import math
from pathlib import Path
import gmsh
from ops import ROOT, disks

MOTORS = {
    'sustainer': (1.5625 * .0254, .1875 * .0254, .125 * .0254),
    'booster': (2.5625 * .0254, .25 * .0254, .1875 * .0254),
}
ANGLE = .5
LENGTH = .0005

def create(motor, casing, angle=ANGLE, length=LENGTH, suffix=''):
    ri, thickness, shell = MOTORS[motor]
    rp, ro = ri + thickness, ri + thickness + shell
    half = math.radians(angle) / 2
    output = ROOT / 'geometry'
    output.mkdir(parents=True, exist_ok=True)
    name = f'{motor}_{casing}_sector{suffix}'
    gmsh.clear()
    gmsh.model.add(name)
    gmsh.option.setString('Geometry.OCCTargetUnit', 'M')
    def point(r, a):
        return gmsh.model.occ.addPoint(r * math.sin(a), 0, r * math.cos(a))
    def sector(a, b):
        origin = gmsh.model.occ.addPoint(0, 0, 0)
        p = [point(a, -half), point(b, -half), point(b, half), point(a, half)]
        edges = [gmsh.model.occ.addLine(p[0], p[1]),
                 gmsh.model.occ.addCircleArc(p[1], origin, p[2]),
                 gmsh.model.occ.addLine(p[2], p[3]),
                 gmsh.model.occ.addCircleArc(p[3], origin, p[0])]
        face = gmsh.model.occ.addPlaneSurface([gmsh.model.occ.addCurveLoop(edges)])
        return next(t for d, t in gmsh.model.occ.extrude([(2, face)], 0, length, 0) if d == 3)
    bodies = [sector(ri, rp), sector(rp, ro)]
    gmsh.model.occ.fragment([(3, bodies[0])], [(3, bodies[1])])
    gmsh.model.occ.synchronize()
    actual = []
    for dim, tag in gmsh.model.getEntities(3):
        center = gmsh.model.occ.getCenterOfMass(dim, tag)
        material = 'phenolic' if math.hypot(center[0], center[2]) < rp else casing
        gmsh.model.setEntityName(dim, tag, material)
        actual.append((material, gmsh.model.occ.getMass(dim, tag)))
    assert sorted(x[0] for x in actual) == sorted(['phenolic', casing])
    path = output / (name + '.step')
    gmsh.write(str(path))
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    # Reimport the exact exported file into an empty model. This catches unit
    # errors in STEP export rather than merely checking the in-memory geometry.
    gmsh.clear()
    gmsh.model.add(name + '_roundtrip')
    gmsh.option.setString('Geometry.OCCTargetUnit', 'M')
    gmsh.model.occ.importShapes(str(path))
    gmsh.model.occ.synchronize()
    volumes = gmsh.model.getEntities(3)
    assert len(volumes) == 2, volumes
    measured = sorted(gmsh.model.occ.getMass(d, t) for d, t in volumes)
    expected = sorted([.5 * math.radians(angle) * length * (rp**2 - ri**2),
                       .5 * math.radians(angle) * length * (ro**2 - rp**2)])
    for a, b in zip(measured, expected):
        assert math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-16), (a, b)
    bbox = gmsh.model.getBoundingBox(-1, -1)
    # OCC boxes contain a small geometric tolerance.
    assert abs((bbox[4] - bbox[1]) - length) < 1e-6, bbox
    return dict(case=f'{motor}_{casing}', step_file=path.name, units='m',
                axis='global Y', angle_deg=angle, length_m=length,
                inner_radius_m=ri, phenolic_outer_radius_m=rp, outer_radius_m=ro,
                phenolic_thickness_m=thickness, case_thickness_m=shell,
                volumes_m3=dict(actual), roundtrip_volumes_m3=measured,
                expected_sorted_volumes_m3=expected, bounding_box_m=bbox,
                roundtrip_passed=True, radial_cells_per_material=20,
                axial_cells=2, angular_cells=2, expected_elements=160,
                expected_nodes=369)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,help='Generate a separate STEP for one configured sector; preserve original STEP files')
    args = parser.parse_args()
    disks()
    gmsh.initialize()
    try:
        if args.config:
            cfg = json.loads(args.config.read_text())
            motor, casing = cfg['case_id'].split('_')
            g = cfg['geometry']
            suffix = '_' + format(g['angle_deg'],'g').replace('.','p') + 'deg'
            path = ROOT/'geometry'/f'{motor}_{casing}_sector{suffix}.step'
            assert not path.exists(), 'Preserve previously generated geometry'
            result = create(motor,casing,g['angle_deg'],g['length_m'],suffix)
            for key in ['inner_radius_m','phenolic_outer_radius_m','outer_radius_m']:
                assert math.isclose(result[key],g[key],abs_tol=1e-12)
            result.update(phenolic_radial_cells=g['phenolic_radial_rows'],casing_radial_cells=g['aluminium_radial_rows'],
                          expected_elements=cfg['expected_elements'],expected_nodes=cfg['expected_nodes'],
                          config_file=str(args.config),
                          qualification='Exact curved STEP geometry for the configured sector. The native mesh is generated separately as straight-sided SOLID278 elements; CAD arc volumes and finite-element polygon volumes are distinct.')
            result.pop('radial_cells_per_material')
            cases = [result]
            validation_path = ROOT/'geometry'/f'{motor}_{casing}{suffix}_validation.json'
        else:
            cases = [create(m, c) for m in MOTORS for c in ['al', 'cf']]
            validation_path = ROOT/'geometry'/'validation.json'
    finally:
        gmsh.finalize()
    validation_path.write_text(json.dumps(cases, indent=2) + '\n')
    print(json.dumps(cases, indent=2))

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Generate the two-body 0.10 degree STEP geometry for the new motor.

The script uses Gmsh/OpenCASCADE only to author exchange geometry.  The solver
mesh is generated independently by ``prepare_model.py`` so the analysis does
not depend on Gmsh at run time.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).parent.parent / "geometry")
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    g = cfg["geometry"]

    import gmsh

    args.output.mkdir(parents=True, exist_ok=True)
    gmsh.initialize()
    try:
        gmsh.model.add("newmotor_phenolic_v0")
        gmsh.option.setString("Geometry.OCCTargetUnit", "M")
        half = math.radians(g["angle_deg"] / 2.0)

        def xyz(radius: float, angle: float, y: float = 0.0) -> tuple[float, float, float]:
            return radius * math.sin(angle), y, radius * math.cos(angle)

        def sector(r0: float, r1: float) -> int:
            c = gmsh.model.occ.addPoint(0.0, 0.0, 0.0)
            p0 = gmsh.model.occ.addPoint(*xyz(r0, -half))
            p1 = gmsh.model.occ.addPoint(*xyz(r1, -half))
            p2 = gmsh.model.occ.addPoint(*xyz(r1, half))
            p3 = gmsh.model.occ.addPoint(*xyz(r0, half))
            curves = (
                gmsh.model.occ.addLine(p0, p1),
                gmsh.model.occ.addCircleArc(p1, c, p2),
                gmsh.model.occ.addLine(p2, p3),
                gmsh.model.occ.addCircleArc(p3, c, p0),
            )
            face = gmsh.model.occ.addPlaneSurface((gmsh.model.occ.addCurveLoop(curves),))
            return next(tag for dim, tag in gmsh.model.occ.extrude(((2, face),), 0.0, g["length_m"], 0.0) if dim == 3)

        raw = (
            sector(g["inner_radius_m"], g["phenolic_outer_radius_m"]),
            sector(g["phenolic_outer_radius_m"], g["outer_radius_m"]),
        )
        gmsh.model.occ.fragment(tuple((3, tag) for tag in raw), ())
        gmsh.model.occ.removeAllDuplicates()
        gmsh.model.occ.synchronize()

        volumes = []
        for dim, tag in gmsh.model.getEntities(3):
            x, _, z = gmsh.model.occ.getCenterOfMass(dim, tag)
            radius = math.hypot(x, z)
            name = "phenolic" if radius < g["phenolic_outer_radius_m"] else "aluminium"
            gmsh.model.setEntityName(dim, tag, name)
            group = gmsh.model.addPhysicalGroup(dim, (tag,))
            gmsh.model.setPhysicalName(dim, group, name)
            volumes.append({"name": name, "tag": tag, "volume_m3": gmsh.model.occ.getMass(dim, tag)})

        volumes.sort(key=lambda item: item["name"], reverse=True)
        if {item["name"] for item in volumes} != {"phenolic", "aluminium"}:
            raise RuntimeError(f"Unexpected volume inventory: {volumes}")
        gmsh.write(str(args.output / "newmotor_phenolic_v0.step"))
        gmsh.write(str(args.output / "newmotor_phenolic_v0.brep"))
        report = {
            "units": "m",
            "axis": "global Y",
            "angle_deg": g["angle_deg"],
            "length_m": g["length_m"],
            "full_ring_scale_factor": g["full_ring_scale_factor"],
            "radii_m": [g["inner_radius_m"], g["phenolic_outer_radius_m"], g["outer_radius_m"]],
            "volumes": volumes,
        }
        (args.output / "geometry_validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    finally:
        gmsh.finalize()


if __name__ == "__main__":
    main()


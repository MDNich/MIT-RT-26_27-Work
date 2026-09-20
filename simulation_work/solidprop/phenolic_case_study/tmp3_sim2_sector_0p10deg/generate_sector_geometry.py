#!/usr/bin/env python3
"""Generate the corrected, self-contained 0.10 degree Simulation 2 sector.

Geometry units are millimetres.  The cylinder axis is global Y, matching the
source Workbench model.  Four adjacent annular volumes are imprinted so their
interfaces are topologically compatible with a conformal swept mesh.
"""

from __future__ import annotations

import json
import math
import pathlib

import gmsh


ROOT = pathlib.Path(__file__).resolve().parent
ANGLE_DEG = 0.10
Y0_MM = 914.4
LENGTH_MM = 50.0

# Correct nominal radii.  The corresponding diameters are
# 133.350, 135.890, 136.525, 142.875 and 152.400 mm.
LAYERS = (
    ("phe0_inner", 66.6750, 67.9450),
    ("epoxy", 67.9450, 68.2625),
    ("phe1_outer", 68.2625, 71.4375),
    ("aluminium", 71.4375, 76.2000),
)


def point_on_radius(radius_mm: float, angle_rad: float) -> tuple[float, float, float]:
    # Sector centred on +Z; Y remains the cylinder axis.
    return (
        radius_mm * math.sin(angle_rad),
        Y0_MM,
        radius_mm * math.cos(angle_rad),
    )


def add_annular_sector(r_inner: float, r_outer: float, a0: float, a1: float) -> int:
    c = gmsh.model.occ.addPoint(0.0, Y0_MM, 0.0)
    pi0 = gmsh.model.occ.addPoint(*point_on_radius(r_inner, a0))
    po0 = gmsh.model.occ.addPoint(*point_on_radius(r_outer, a0))
    po1 = gmsh.model.occ.addPoint(*point_on_radius(r_outer, a1))
    pi1 = gmsh.model.occ.addPoint(*point_on_radius(r_inner, a1))

    radial_0 = gmsh.model.occ.addLine(pi0, po0)
    outer_arc = gmsh.model.occ.addCircleArc(po0, c, po1)
    radial_1 = gmsh.model.occ.addLine(po1, pi1)
    inner_arc = gmsh.model.occ.addCircleArc(pi1, c, pi0)
    loop = gmsh.model.occ.addCurveLoop((radial_0, outer_arc, radial_1, inner_arc))
    face = gmsh.model.occ.addPlaneSurface((loop,))
    extruded = gmsh.model.occ.extrude(((2, face),), 0.0, LENGTH_MM, 0.0)
    return next(tag for dim, tag in extruded if dim == 3)


def main() -> None:
    gmsh.initialize()
    try:
        gmsh.model.add("simulation2_sector_0p10deg")
        gmsh.option.setString("Geometry.OCCTargetUnit", "MM")
        half = math.radians(ANGLE_DEG / 2.0)
        source_volumes = [
            add_annular_sector(r0, r1, -half, half) for _, r0, r1 in LAYERS
        ]

        # Imprint the coincident interfaces.  This retains four volumes while
        # making shared radial interfaces suitable for a conformal mesh.
        gmsh.model.occ.fragment(tuple((3, tag) for tag in source_volumes), ())
        gmsh.model.occ.removeAllDuplicates()
        gmsh.model.occ.synchronize()

        volumes = []
        for dim, tag in gmsh.model.getEntities(3):
            x, _, z = gmsh.model.occ.getCenterOfMass(dim, tag)
            radius = math.hypot(x, z)
            name, r0, r1 = min(
                LAYERS,
                key=lambda layer: abs(radius - 0.5 * (layer[1] + layer[2])),
            )
            gmsh.model.setEntityName(dim, tag, name)
            group = gmsh.model.addPhysicalGroup(3, (tag,))
            gmsh.model.setPhysicalName(3, group, name)
            bbox = gmsh.model.getBoundingBox(dim, tag)
            volume_mm3 = gmsh.model.occ.getMass(dim, tag)
            volumes.append(
                {
                    "name": name,
                    "entity_tag": tag,
                    "r_inner_mm": r0,
                    "r_outer_mm": r1,
                    "radial_thickness_mm": r1 - r0,
                    "volume_mm3": volume_mm3,
                    "bounding_box_mm": bbox,
                }
            )

        volumes.sort(key=lambda item: item["r_inner_mm"])
        if [item["name"] for item in volumes] != [item[0] for item in LAYERS]:
            raise RuntimeError(f"Unexpected radial volume ordering: {volumes}")

        step_path = ROOT / "simulation2_sector_0p10deg.step"
        brep_path = ROOT / "simulation2_sector_0p10deg.brep"
        gmsh.write(str(step_path))
        gmsh.write(str(brep_path))

        report = {
            "angle_deg": ANGLE_DEG,
            "full_ring_scale_factor": 360.0 / ANGLE_DEG,
            "axis": "global Y",
            "axial_start_mm": Y0_MM,
            "axial_length_mm": LENGTH_MM,
            "volume_count": len(volumes),
            "volumes": volumes,
            "step_file": step_path.name,
            "brep_file": brep_path.name,
        }
        (ROOT / "geometry_validation.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    finally:
        gmsh.finalize()


if __name__ == "__main__":
    main()

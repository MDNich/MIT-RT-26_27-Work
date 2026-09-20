"""Configure and generate the detailed 0.10 degree sector mesh in Mechanical."""

import os
import traceback
from System.IO import File
from Ansys.Mechanical.DataModel.Enums import *


ROOT = r"C:\ansys_sector_sim2"
REPORT = os.path.join(ROOT, "mesh_sector_report.txt")
lines = []


def emit(text=""):
    try:
        lines.append(unicode(text))
    except Exception:
        lines.append(u"<unprintable>")
    File.WriteAllText(REPORT, u"\r\n".join(lines))


def safe(getter, fallback="<unavailable>"):
    try:
        return getter()
    except Exception:
        return fallback


def selection(ids):
    info = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    info.Ids = list(ids)
    return info


def edge_length(edge):
    value = edge.Length
    try:
        return float(value.Value)
    except Exception:
        return float(value)


def add_edge_divisions(mesh, name, edge_ids, divisions):
    control = mesh.AddSizing()
    control.Name = name
    control.Location = selection(edge_ids)
    control.Type = SizingType.NumberOfDivisions
    control.NumberOfDivisions = divisions
    try:
        control.Behavior = SizingBehavior.Hard
    except Exception:
        pass
    emit("Sizing {}: edges={} divisions={}".format(name, len(edge_ids), divisions))
    return control


try:
    model = ExtAPI.DataModel.Project.Model
    mesh = model.Mesh

    # Remove only mesh controls inherited from the full-ring project.  The
    # source project is untouched; this script runs on the copied project.
    for child in list(mesh.Children):
        emit("Deleting inherited mesh control: {}".format(safe(lambda: child.Name)))
        child.Delete()

    bodies = []
    for part in model.Geometry.Children:
        for child in part.Children:
            if child.GetType().Name == "Body":
                bodies.append(child)

    layers = (
        ("phe0_inner", "PHENOLIC_PYROLYSIS", 1.2700, 64),
        ("epoxy", "EPOXY", 0.3175, 16),
        ("phe1_outer", "PHENOLIC_VIRGIN", 3.1750, 64),
        ("aluminium", "ALUMINUM", 4.7625, 32),
    )
    if len(bodies) != len(layers):
        raise RuntimeError("Expected four geometry bodies, found {}".format(len(bodies)))

    # Geometry import order is radial order; verify it independently by volume.
    bodies.sort(key=lambda body: float(body.GetGeoBody().Volume))
    # The epoxy is smallest by volume, so volume sorting is not radial ordering.
    # Recover radial order from the known STEP part suffix retained by Mechanical.
    bodies.sort(key=lambda body: int(body.Parent.Name.rsplit(".", 1)[-1]))

    axial_edges = []
    circumferential_edges = []
    radial_sets = []
    body_ids = []

    for body, layer in zip(bodies, layers):
        name, material, thickness, radial_divisions = layer
        body.Name = name
        body.Material = material
        geo_body = body.GetGeoBody()
        body_ids.append(geo_body.Id)
        radial_ids = []
        local_axial = []
        local_circ = []
        edge_summary = []
        for edge in geo_body.Edges:
            length = edge_length(edge)
            edge_summary.append((edge.Id, length))
            if abs(length - 50.0) < 0.1:
                local_axial.append(edge.Id)
            elif abs(length - thickness) < max(0.002, thickness * 0.002):
                radial_ids.append(edge.Id)
            elif 0.10 < length < 0.15:
                local_circ.append(edge.Id)

        if len(local_axial) != 4 or len(radial_ids) != 4 or len(local_circ) != 4:
            raise RuntimeError(
                "Unexpected edge classification for {}: axial={}, radial={}, circum={}, all={}".format(
                    name, local_axial, radial_ids, local_circ, edge_summary
                )
            )
        axial_edges.extend(local_axial)
        circumferential_edges.extend(local_circ)
        radial_sets.append((name, radial_ids, radial_divisions))
        emit("Body {}: material={} volume={} edge_lengths={}".format(
            name, material, safe(lambda: geo_body.Volume), edge_summary
        ))

    mesh.ElementSize = Quantity("0.5 [mm]")
    try:
        mesh.ElementOrder = ElementOrder.Linear
    except Exception:
        pass

    # Each body is a simple extruded annular-sector prism and is sweepable.
    for body, layer in zip(bodies, layers):
        method = mesh.AddAutomaticMethod()
        method.Name = "Sweep - {}".format(layer[0])
        method.Location = selection([body.GetGeoBody().Id])
        method.Method = MethodType.Sweep

    add_edge_divisions(mesh, "Axial - 100 divisions", axial_edges, 100)
    add_edge_divisions(mesh, "Angular - 2 divisions", circumferential_edges, 2)
    for name, radial_ids, divisions in radial_sets:
        add_edge_divisions(
            mesh,
            "Radial {} - {} divisions".format(name, divisions),
            radial_ids,
            divisions,
        )

    emit("Generating mesh...")
    mesh.GenerateMesh()
    mesh_data = ExtAPI.DataModel.Project.Model.Analyses[0].MeshData
    emit("MESH_GENERATED=True")
    emit("Node count={}".format(safe(lambda: mesh_data.Nodes.Count)))
    emit("Element count={}".format(safe(lambda: mesh_data.Elements.Count)))
    emit("Expected nominal hexahedra=35200")
except Exception:
    emit("MESH_GENERATED=False")
    emit(traceback.format_exc())


"""Validate saved mesh topology and per-body element counts in Mechanical."""

import os
import traceback
from System.IO import File


ROOT = r"C:\ansys_sector_sim2"
OUTPUT = os.path.join(ROOT, "mesh_validation.txt")
lines = []


def emit(text=""):
    lines.append(unicode(text))
    File.WriteAllText(OUTPUT, u"\r\n".join(lines))


def safe(getter, fallback="<unavailable>"):
    try:
        return getter()
    except Exception:
        return fallback


try:
    analysis = ExtAPI.DataModel.Project.Model.Analyses[0]
    mesh_data = analysis.MeshData
    emit("SIMULATION 2 SECTOR MESH VALIDATION")
    emit("Nodes={}".format(mesh_data.Nodes.Count))
    emit("Elements={}".format(mesh_data.Elements.Count))

    topology_counts = {}
    for element in mesh_data.Elements:
        node_count = len(element.NodeIds)
        element_type = safe(lambda: unicode(element.Type), "unknown")
        key = (element_type, node_count)
        topology_counts[key] = topology_counts.get(key, 0) + 1
    for key in sorted(topology_counts):
        emit("Element topology type={} nodes_per_element={} count={}".format(
            key[0], key[1], topology_counts[key]
        ))

    emit("PER-BODY REGIONS")
    for assembly in ExtAPI.DataModel.GeoData.Assemblies:
        for part in assembly.Parts:
            for body in part.Bodies:
                region = mesh_data.MeshRegionById(body.Id)
                emit("{} | geo_id={} | nodes={} | elements={}".format(
                    body.Name,
                    body.Id,
                    safe(lambda: region.Nodes.Count),
                    safe(lambda: region.Elements.Count),
                ))
    emit("VALIDATION_OK=True")
except Exception:
    emit("VALIDATION_OK=False")
    emit(traceback.format_exc())


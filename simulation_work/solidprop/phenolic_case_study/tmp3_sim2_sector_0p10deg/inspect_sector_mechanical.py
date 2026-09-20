"""Inventory the sector model after Workbench refresh (Mechanical IronPython)."""

import os
import traceback
from System.IO import File


ROOT = r"C:\ansys_sector_sim2"
OUTPUT = os.path.join(ROOT, "mechanical_sector_inventory.txt")
lines = []


def safe(getter, fallback="<unavailable>"):
    try:
        return getter()
    except Exception:
        return fallback


def emit(text=""):
    try:
        lines.append(unicode(text))
    except Exception:
        lines.append(u"<unprintable>")


def walk(obj, depth=0):
    emit(u"{}{} | {} | id={} | suppressed={} | state={}".format(
        u"  " * depth,
        safe(lambda: obj.Name, "<unnamed>"),
        safe(lambda: obj.GetType().FullName, "<unknown>"),
        safe(lambda: obj.ObjectId, "?"),
        safe(lambda: obj.Suppressed, "n/a"),
        safe(lambda: obj.State, "n/a"),
    ))
    for child in safe(lambda: list(obj.Children), []):
        walk(child, depth + 1)


try:
    emit("SIMULATION 2 SECTOR 0.10 DEG MECHANICAL INVENTORY")
    emit("Version: {}".format(safe(lambda: ExtAPI.Application.Version)))
    emit("")
    emit("GEOMETRY")
    assemblies = safe(lambda: list(ExtAPI.DataModel.GeoData.Assemblies), [])
    emit("Assembly count: {}".format(len(assemblies)))
    total_bodies = 0
    for assembly in assemblies:
        parts = safe(lambda: list(assembly.Parts), [])
        emit("Assembly {} | parts={}".format(safe(lambda: assembly.Name), len(parts)))
        for part in parts:
            bodies = safe(lambda: list(part.Bodies), [])
            total_bodies += len(bodies)
            emit("  Part {} | bodies={}".format(safe(lambda: part.Name), len(bodies)))
            for body in bodies:
                emit(
                    "    Body {} | id={} | volume={} | material={} | type={}".format(
                        safe(lambda: body.Name),
                        safe(lambda: body.Id),
                        safe(lambda: body.Volume),
                        safe(lambda: body.Material),
                        safe(lambda: body.BodyType),
                    )
                )
    emit("Total geometry bodies: {}".format(total_bodies))
    emit("")
    emit("MECHANICAL BODIES AND FACES")
    for body in safe(lambda: list(ExtAPI.DataModel.GetObjectsByType(DataModelObjectCategory.Body)), []):
        emit("Body {} | object_id={} | material={} | geo_id={}".format(
            safe(lambda: body.Name), safe(lambda: body.ObjectId),
            safe(lambda: body.Material), safe(lambda: body.GetGeoBody().Id)))
        geo_body = safe(lambda: body.GetGeoBody(), None)
        if geo_body is not None:
            for face in safe(lambda: list(geo_body.Faces), []):
                emit("  Face id={} | area={} | centroid={}".format(
                    safe(lambda: face.Id), safe(lambda: face.Area),
                    safe(lambda: face.Centroid)))
    emit("")
    emit("CONTACT DETAILS")
    for contact in safe(lambda: list(ExtAPI.DataModel.GetObjectsByType(DataModelObjectCategory.ContactRegion)), []):
        emit("{} | id={} | suppressed={} | type={} | behavior={} | formulation={} | contact_ids={} | target_ids={}".format(
            safe(lambda: contact.Name), safe(lambda: contact.ObjectId),
            safe(lambda: contact.Suppressed), safe(lambda: contact.ContactType),
            safe(lambda: contact.Behavior), safe(lambda: contact.ContactFormulation),
            safe(lambda: list(contact.SourceLocation.Ids)),
            safe(lambda: list(contact.TargetLocation.Ids))))
    emit("")
    emit("THERMAL LOAD DETAILS")
    for obj_id in (109, 189, 191, 193, 200):
        obj = safe(lambda oid=obj_id: ExtAPI.DataModel.GetObjectById(oid), None)
        if obj is None:
            emit("id={} | missing".format(obj_id))
            continue
        emit("{} | id={} | type={} | suppressed={} | location_ids={}".format(
            safe(lambda: obj.Name), obj_id, safe(lambda: obj.GetType().FullName),
            safe(lambda: obj.Suppressed), safe(lambda: list(obj.Location.Ids))))
        emit("  State={} Status={}".format(
            safe(lambda: obj.State), safe(lambda: obj.Status)))
        for prop in ("Temperature", "AmbientTemperature", "FilmCoefficient", "Emissivity", "IssueSolveCommand"):
            emit("  {}={}".format(prop, safe(lambda p=prop: getattr(obj, p))))
        if obj_id == 200:
            emit("  InputLength={}".format(safe(lambda: len(obj.Input))))
    emit("")
    emit("MODEL TREE")
    walk(ExtAPI.DataModel.Project.Model)
    emit("")
    emit("APPLICATION MESSAGES")
    message_manager = safe(lambda: ExtAPI.Application.MessageManager, None)
    if message_manager is not None:
        for message in safe(lambda: list(message_manager.GetMessages()), []):
            emit("{} | {}".format(
                safe(lambda m=message: m.Severity),
                safe(lambda m=message: m.DisplayString, safe(lambda m=message: unicode(m)))))
    emit("")
    emit("SOLUTION API")
    analysis = safe(lambda: ExtAPI.DataModel.Project.Model.Analyses[0], None)
    if analysis is not None:
        emit("AnalysisStatus={} SolutionStatus={}".format(
            safe(lambda: analysis.Status), safe(lambda: analysis.Solution.Status)))
        emit("SkipSolveCommand={}".format(safe(lambda: analysis.Solution.SkipSolveCommand)))
        for method in safe(lambda: list(analysis.Solution.GetType().GetMethods()), []):
            if safe(lambda m=method: m.Name, "") == "Solve":
                emit("Solve overload: {}".format(method))
        emit("Solution methods={}".format(
            [name for name in dir(analysis.Solution) if "olv" in name or "tat" in name]))
    emit("")
    emit("SOLVE CONFIGURATIONS")
    for configuration in ExtAPI.Application.SolveConfigurations:
        settings = configuration.SolveProcessSettings
        emit("{} | default={} | distributed={} | cores={}".format(
            safe(lambda: configuration.Name),
            safe(lambda: configuration.Default),
            safe(lambda: settings.DistributeSolution),
            safe(lambda: settings.MaxNumberOfCores),
        ))
except Exception:
    emit("")
    emit("INVENTORY ERROR")
    emit(traceback.format_exc())
finally:
    File.WriteAllText(OUTPUT, u"\r\n".join(lines))

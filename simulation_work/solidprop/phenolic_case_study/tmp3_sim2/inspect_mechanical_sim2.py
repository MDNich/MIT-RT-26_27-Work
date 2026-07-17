"""Read-only inventory of the copied Mechanical model.

Run inside Mechanical's IronPython interpreter through ``inspect_sim2.wbjn``.
The report is deliberately plain text so it can be inspected from macOS while
Mechanical remains the authority for object names and editable properties.
"""

import os
import traceback

from System.IO import File


ROOT = r"C:\ansys_sim2"
OUTPUT = os.path.join(ROOT, "mechanical_inventory.txt")
lines = []


def add(text=""):
    try:
        lines.append(unicode(text))
    except Exception:
        lines.append(u"<unprintable>")


def safe(getter, fallback="<unavailable>"):
    try:
        return getter()
    except Exception:
        return fallback


def type_name(obj):
    return safe(lambda: obj.GetType().FullName, "<unknown type>")


def dump_properties(obj, indent):
    prefix = " " * indent
    properties = safe(lambda: list(obj.Properties), [])
    for prop in properties:
        name = safe(lambda: prop.Name, "?")
        caption = safe(lambda: prop.Caption, "")
        value = "<unavailable>"
        for attribute in ("InternalValue", "Value", "StringValue"):
            try:
                value = getattr(prop, attribute)
                break
            except Exception:
                pass
        add(
            "{}PROPERTY {} | {} = {}".format(
                prefix,
                name,
                caption,
                value,
            )
        )


def dump_object(obj, depth=0):
    prefix = "  " * depth
    add(
        "{}OBJECT {} | {} | id={}".format(
            prefix,
            safe(lambda: obj.Name, "<unnamed>"),
            type_name(obj),
            safe(lambda: obj.ObjectId, "?"),
        )
    )
    dump_properties(obj, 2 * depth + 2)
    children = safe(lambda: list(obj.Children), [])
    for child in children:
        dump_object(child, depth + 1)


try:
    add("MECHANICAL SIMULATION 2 INVENTORY")
    add("Project directory: {}".format(ROOT))
    add("Product version: {}".format(safe(lambda: ExtAPI.Application.Version)))
    add("")
    File.WriteAllText(OUTPUT, "\r\n".join(lines))

    model = ExtAPI.DataModel.Project.Model
    dump_object(model)

    add("")
    add("SOLVE CONFIGURATIONS")
    for configuration in ExtAPI.Application.SolveConfigurations:
        settings = configuration.SolveProcessSettings
        add(
            "{} | default={} | distributed={} | cores={} | working dir={}".format(
                safe(lambda: configuration.Name),
                safe(lambda: configuration.Default),
                safe(lambda: settings.DistributeSolution),
                safe(lambda: settings.MaxNumberOfCores),
                safe(lambda: settings.WorkingDirectory),
            )
        )
except Exception:
    add("")
    add("INVENTORY ERROR")
    add(traceback.format_exc())
finally:
    File.WriteAllText(OUTPUT, "\r\n".join(lines))
    ExtAPI.Log.WriteMessage("Inventaire Simulation 2 ecrit: " + OUTPUT)

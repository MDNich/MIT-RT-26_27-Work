# -*- coding: utf-8 -*-
"""Run in Mechanical 2026 R1: Automation > Scripting, IronPython engine.

Save the project first. Import Sherlock's output.xml into this system's
Engineering Data and Refresh Materials before running this script.
Reads the latest generated mapping as text; does not execute output.py.
Sets existing bodies' Material properties and verifies them. Does not generate
geometry, named selections, meshes, or solutions, and does not save the project.
"""
from __future__ import print_function

import datetime
import hashlib
import io
import os
import re

PROJECT_DIR = r"Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1"
SOURCE_SCRIPT = os.path.join(PROJECT_DIR, "powerboardsim_v1_files", "dp0",
                             "global", "MECH", "SYS", "output.py")
REPORT_DIR = os.path.join(PROJECT_DIR, "outputs")
# Verified in this project's saved EngineeringData.xml on 2026-10-04:
# CUIVRE matches exported COPPER: 8900 kg/m3, 113 GPa, nu=0.34,
# k=385 W/(m K), CTE=1.76e-5 /K. Prefer COPPER if that name is available.
MATERIAL_ALIASES = {"COPPER": "CUIVRE"}


def read_mapping(path):
    with io.open(path, "r", encoding="utf-8-sig") as handle:
        source = handle.read()
    pairs = re.findall(r"^\s*initGeometry\('([^']+)','([^']+)'\)\s*$",
                       source, re.MULTILINE)
    mapping = {}
    for name, material in pairs:
        if name in mapping and mapping[name] != material:
            raise RuntimeError("Conflicting Sherlock mapping for " + name)
        mapping[name] = material
    if mapping.get("PCB") != "PCB":
        raise RuntimeError("This recovery script expects the uniform PCB2 export "
                           "with the PCB body mapped to the PCB material.")
    if not any(name.startswith("COMP_") for name in mapping):
        raise RuntimeError("No component assignments found in Sherlock's export.")
    return mapping, hashlib.sha256(source.encode("utf-8")).hexdigest()


def canonical_name(label, mapping):
    """Match a complete leaf name, never a substring such as C1 inside C10."""
    label = str(label).strip()
    if label in mapping:
        return label
    # Recognized STEP import wrappers, also handled by Sherlock's own script.
    label = re.sub(r"\|Surface[^|]*$", "", label)
    leaf = re.split(r"[\\/|]", label)[-1].strip()
    leaf = re.sub(r"\[\d+\]$", "", leaf).strip()
    return leaf if leaf in mapping else None


def build_plan(bodies, mapping, material_names):
    plan, unmatched, conflicts = [], [], []
    owners = {}
    for body in bodies:
        labels = [str(body.Name)]
        try:
            labels.append(str(body.GetGeoBody().Name))
        except Exception:
            pass  # A body may have no underlying CAD object.
        matches = set(canonical_name(label, mapping) for label in labels)
        matches.discard(None)
        if not matches:
            unmatched.append({"name": str(body.Name), "id": int(body.ObjectId)})
            continue
        if len(matches) != 1:
            conflicts.append("Conflicting body/CAD names for " + str(body.Name))
            continue
        name = list(matches)[0]
        if name in owners:
            conflicts.append("Multiple bodies match " + name + ": " +
                             owners[name] + ", " + str(body.Name))
        owners[name] = str(body.Name)
        target = mapping[name]
        if target not in material_names:
            target = MATERIAL_ALIASES.get(target, target)
        row = {"id": int(body.ObjectId), "body": str(body.Name),
               "sherlock_name": name, "before": str(body.Material),
               "sherlock_material": mapping[name], "target": target}
        plan.append((body, row))
    missing_materials = sorted(set(row["target"] for body, row in plan)
                               - set(material_names))
    errors = list(conflicts)
    if not plan:
        errors.append("No bodies match the Sherlock export. See the body inventory.")
    if "PCB" not in owners:
        errors.append("The exported PCB body was not found; check the active model.")
    if missing_materials:
        errors.append("Import output.xml into this system's Engineering Data, "
                      "add these materials, and Refresh Materials: " +
                      ", ".join(missing_materials))
    return plan, unmatched, sorted(set(mapping) - set(owners)), errors


def apply_plan(plan, report):
    attempted = []
    try:
        for body, row in plan:
            if str(body.Material) != row["target"]:
                attempted.append((body, row))
                body.Material = row["target"]
            row["after"] = str(body.Material)
            if row["after"] != row["target"]:
                raise RuntimeError("Material readback mismatch on " + row["body"])
        report["changed_bodies"] = len(attempted)
        report["verified_bodies"] = len(plan)
    except Exception as exc:
        report["assignment_error"] = str(exc)
        report["rollback_errors"] = []
        for body, row in reversed(attempted):
            try:
                body.Material = row["before"]
                if str(body.Material) != row["before"]:
                    raise RuntimeError("Previous assignment did not restore")
                row["after"] = str(body.Material)
            except Exception as restore_exc:
                report["rollback_errors"].append(row["body"] + ": " + str(restore_exc))
        report["status"] = ("ROLLBACK_INCOMPLETE" if report["rollback_errors"]
                            else "ASSIGNMENT_FAILED_ROLLED_BACK")
        raise


def report_lines(value, indent=0):
    """Plain-text report without json/_json, unavailable in some ACT sessions."""
    prefix = u" " * indent
    if isinstance(value, dict):
        lines = []
        for key in sorted(value):
            lines.append(prefix + type(u"")(key) + u":")
            lines.extend(report_lines(value[key], indent + 2))
        return lines or [prefix + u"{}"]
    if isinstance(value, (list, tuple)):
        lines = []
        for index, item in enumerate(value):
            lines.append(prefix + u"[{0}]".format(index))
            lines.extend(report_lines(item, indent + 2))
        return lines or [prefix + u"[]"]
    return [prefix + type(u"")(repr(value))]


def save_report(path, report):
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(u"Sherlock material assignment report\n\n")
        handle.write(u"\n".join(report_lines(report)) + u"\n")


def notify(message):
    print(message)
    ExtAPI.Log.WriteMessage(message)
    try:
        import Ansys
        ExtAPI.Application.Messages.Add(Ansys.Mechanical.Application.Message(
            message, MessageSeverityType.Info))
    except Exception:
        pass  # The scripting console and application log still contain the result.


def main():
    stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    if not os.path.isdir(REPORT_DIR):
        os.makedirs(REPORT_DIR)
    report_path = os.path.join(REPORT_DIR, "sherlock_material_assignment_" + stamp + ".txt")
    report = {"time_utc": stamp, "source": SOURCE_SCRIPT, "status": "PREFLIGHT"}
    try:
        mapping, source_hash = read_mapping(SOURCE_SCRIPT)
        report["mapping_sha256"] = source_hash
        report["mapping_entries"] = len(mapping)
        model = ExtAPI.DataModel.Project.Model
        bodies = list(model.Geometry.GetChildren(DataModelObjectCategory.Body, True))
        materials = model.Materials.GetChildren(DataModelObjectCategory.Material, True)
        names = [str(material.Name) for material in materials]
        report["available_materials"] = sorted(names)
        plan, unmatched, absent, errors = build_plan(bodies, mapping, names)
        report["assignments"] = [row for body, row in plan]
        report["unmatched_bodies_unchanged"] = unmatched
        report["exported_bodies_not_found"] = absent
        report["preflight_errors"] = errors
        if errors:
            report["status"] = "PREFLIGHT_FAILED_NO_ASSIGNMENTS_CHANGED"
            raise RuntimeError("\n".join(errors))
        # Record the original assignments before making any change.
        report["status"] = "READY"
        save_report(report_path, report)
        apply_plan(plan, report)
        report["status"] = "VERIFIED" if not absent else "PARTIAL_VERIFIED"
        save_report(report_path, report)
        summary = ("Sherlock materials: {0} bodies verified, {1} changed; "
                   "{2} export names not found; {3} other bodies unchanged. Report: {4}").format(
                       len(plan), report["changed_bodies"], len(absent), len(unmatched), report_path)
        notify(summary)
        if absent:
            notify("Unmatched export names: " + ", ".join(absent))
    except Exception as exc:
        report["error"] = str(exc)
        if report["status"] == "PREFLIGHT":
            report["status"] = "PREFLIGHT_FAILED_NO_ASSIGNMENTS_CHANGED"
        save_report(report_path, report)
        notify("Sherlock material assignment stopped: " + str(exc) + ". Report: " + report_path)
        raise


if "ExtAPI" in globals():
    main()

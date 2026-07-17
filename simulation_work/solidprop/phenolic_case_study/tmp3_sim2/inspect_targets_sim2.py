"""Targeted Mechanical API inventory for Simulation 2 configuration."""

from System.IO import File


OUTPUT = r"C:\ansys_sim2\mechanical_targets.txt"
lines = []


def save():
    File.WriteAllText(OUTPUT, u"\r\n".join(lines))


def emit(text):
    try:
        lines.append(unicode(text))
    except Exception:
        lines.append(u"<unprintable>")
    save()


def describe(object_id):
    obj = ExtAPI.DataModel.GetObjectById(object_id)
    emit(u"OBJECT {} | {} | id={}".format(
        obj.Name, obj.GetType().FullName, object_id
    ))
    attributes = (
        "NumberOfDivisions",
        "ElementSize",
        "Type",
        "Behavior",
        "BiasType",
        "BiasFactor",
        "Geometry",
        "Location",
        "Input",
        "IssueSolveCommand",
        "Suppressed",
        "NumberOfSteps",
        "InitialTimeStep",
        "MinimumTimeStep",
        "MaximumTimeStep",
        "StepEndTime",
        "FilmCoefficient",
        "AmbientTemperature",
        "Expression",
    )
    for attribute in attributes:
        try:
            emit(u"  ATTR {} = {}".format(attribute, getattr(obj, attribute)))
        except Exception as exc:
            emit(u"  ATTR {} = <{}>".format(attribute, exc.GetType().Name))
emit(u"SIMULATION 2 TARGETED INVENTORY")
for target_id in (156, 177, 199, 200, 110, 104, 189, 191, 201, 202):
    try:
        describe(target_id)
    except Exception as exc:
        emit(u"OBJECT id={} FAILED: {}".format(target_id, exc))

emit(u"SOLUTION EXPRESSIONS")
solution = ExtAPI.DataModel.GetObjectById(105)
for child in solution.Children:
    if hasattr(child, "Expression"):
        emit(u"  {} = {}".format(child.Name, child.Expression))

emit(u"SOLVE CONFIGURATIONS")
for configuration in ExtAPI.Application.SolveConfigurations:
    settings = configuration.SolveProcessSettings
    emit(u"  {} default={} distributed={} cores={}".format(
        configuration.Name,
        configuration.Default,
        settings.DistributeSolution,
        settings.MaxNumberOfCores,
    ))

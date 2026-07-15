"""IronPython-safe Mechanical configuration for native UserMatTh."""

import os

from Ansys.Mechanical.DataModel.Enums import PythonCodeTargetCallback
from System.IO import File


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FORTRAN_SOURCE = os.path.join(SCRIPT_DIR, "usermatth.F")
APDL_SOURCE = os.path.join(SCRIPT_DIR, "phenolic_pyrolysis_native.apdl")


def first(items, description):
    if not items:
        raise RuntimeError("Objet Mechanical introuvable: " + description)
    return items[0]


if not os.path.isfile(FORTRAN_SOURCE):
    raise RuntimeError("Source Fortran introuvable: " + FORTRAN_SOURCE)
if not os.path.isfile(APDL_SOURCE):
    raise RuntimeError("Commandes APDL introuvables: " + APDL_SOURCE)

apdl_text = File.ReadAllText(APDL_SOURCE)
model = ExtAPI.DataModel.Project.Model
analysis = first(list(model.Analyses), "analyse Thermique transitoire")

# Copy once now. The event callback below refreshes this before every solve.
if os.path.isdir(analysis.WorkingDir):
    File.Copy(
        FORTRAN_SOURCE,
        os.path.join(analysis.WorkingDir, "usermatth.F"),
        True,
    )
os.environ["ANS_USE_UPF"] = "TRUE"

body_candidates = []
for candidate in ExtAPI.DataModel.GetObjectsByName("phe0"):
    if (
        hasattr(candidate, "Material")
        and hasattr(candidate, "Children")
        and hasattr(candidate, "AddCommandSnippet")
    ):
        body_candidates.append(candidate)
body = first(body_candidates, "corps phe0")
if body.Material != "PHENOLIC_PYROLYSIS":
    body.Material = "PHENOLIC_PYROLYSIS"

body_command = None
for child in body.Children:
    if hasattr(child, "Input"):
        current = child.Input or ""
        if "/UPF" in current or "TB,USER" in current or "PYRA" in current:
            body_command = child
            break
if body_command is None:
    body_command = body.AddCommandSnippet()
body_command.Name = "Pyrolyse phenolique - UserMatTh Fortran"
body_command.Input = apdl_text
body_command.Suppressed = False

solver_command = None
for candidate in ExtAPI.DataModel.GetObjectsByName("Commandes (APDL)"):
    if hasattr(candidate, "Input"):
        current = candidate.Input or ""
        if "THOPT" in current or "OUTRES,SVAR" in current:
            solver_command = candidate
            break
if solver_command is not None:
    solver_command.Input = "THOPT,FULL\nOUTRES,SVAR,ALL\n/GRAPHICS,FULL"
    solver_command.Suppressed = False
else:
    ExtAPI.Log.WriteWarning(
        "Snippet SVAR introuvable; conserver OUTRES,SVAR,ALL."
    )

initial_condition = None
for child in analysis.Children:
    if hasattr(child, "InitialTemperatureValue"):
        initial_condition = child
        break
if initial_condition is not None:
    initial_condition.InitialTemperatureValue = Quantity("22 [C]")
else:
    ExtAPI.Log.WriteWarning("Objet Temperature initiale introuvable.")

callback_text = '''def before_solve(this, analysis):# Do not edit this line
    import os
    from System.IO import File

    source = {source!r}
    solver_dir = analysis.WorkingDir
    target = os.path.join(solver_dir, "usermatth.F")
    File.Copy(source, target, True)

    ans_root = os.environ.get(
        "AWP_ROOT261", r"C:\\Program Files\\ANSYS Inc\\v261"
    )
    ans_bin = os.path.join(ans_root, "ansys", "bin", "winx64")
    path_items = os.environ.get("PATH", "").split(os.pathsep)
    if ans_bin not in path_items:
        os.environ["PATH"] = ans_bin + os.pathsep + os.environ.get("PATH", "")
    os.environ["ANS_USE_UPF"] = "TRUE"
    ExtAPI.Log.WriteMessage("UserMatTh Fortran copie vers: " + target)
'''.format(source=FORTRAN_SOURCE)

stage_source = None
for candidate in ExtAPI.DataModel.GetObjectsByName(
    "Copie UserMatTh Fortran avant solve"
):
    if hasattr(candidate, "TargetCallback") and hasattr(candidate, "Text"):
        stage_source = candidate
        break
if stage_source is None:
    for candidate in ExtAPI.DataModel.GetObjectsByName("Code Python"):
        if hasattr(candidate, "TargetCallback") and hasattr(candidate, "Text"):
            stage_source = candidate
            break
if stage_source is None:
    stage_source = body.AddPythonCodeEventBased()

stage_source.Name = "Copie UserMatTh Fortran avant solve"
stage_source.TargetCallback = PythonCodeTargetCallback.OnBeforeSolve
stage_source.Text = callback_text
stage_source.Suppressed = False
stage_source.Connect()

default_configuration = None
for configuration in ExtAPI.Application.SolveConfigurations:
    if configuration.Default:
        default_configuration = configuration
        break
if default_configuration is not None:
    solve_settings = default_configuration.SolveProcessSettings
    solve_settings.DistributeSolution = False
    solve_settings.MaxNumberOfCores = 1
else:
    ExtAPI.Log.WriteWarning(
        "Configuration de solve introuvable; faire le premier test sur 1 coeur."
    )

ExtAPI.Log.WriteMessage(
    "Configuration UserMatTh Fortran terminee. Enregistrer le projet."
)

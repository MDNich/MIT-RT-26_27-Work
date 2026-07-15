"""Configure the open Mechanical 2026 R1 model for native UserMatTh.

Run this file once from Mechanical: Automation > Scripting > Open Script,
then Run Script.  It updates the authoritative Mechanical database objects;
editing CAERep.xml or ds.dat directly would only change generated files.
"""

import os

from Ansys.Mechanical.DataModel.Enums import PythonCodeTargetCallback
from System.IO import File


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FORTRAN_SOURCE = os.path.join(SCRIPT_DIR, "usermatth.F")
APDL_SOURCE = os.path.join(SCRIPT_DIR, "phenolic_pyrolysis_native.apdl")


def _first(items, description):
    if not items:
        raise RuntimeError("Objet Mechanical introuvable: " + description)
    return items[0]


def _children_with_attribute(parent, attribute):
    return [child for child in parent.Children if hasattr(child, attribute)]


if not os.path.isfile(FORTRAN_SOURCE):
    raise RuntimeError("Source Fortran introuvable: " + FORTRAN_SOURCE)
if not os.path.isfile(APDL_SOURCE):
    raise RuntimeError("Commandes APDL introuvables: " + APDL_SOURCE)

with open(APDL_SOURCE, "r") as stream:
    apdl_text = stream.read()

model = ExtAPI.DataModel.Project.Model
analysis = _first(list(model.Analyses), "analyse Thermique transitoire")

# Stage a first copy immediately; the callback below refreshes it before
# every subsequent solve.
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
body = _first(body_candidates, "corps phe0")

# Keep the user material assignment explicit.
if body.Material != "PHENOLIC_PYROLYSIS":
    body.Material = "PHENOLIC_PYROLYSIS"

# Replace the old /UPF,usermatth.py body command with the native routine.
body_commands = _children_with_attribute(body, "Input")
pyro_commands = []
for command in body_commands:
    current = command.Input or ""
    if "/UPF" in current or "TB,USER" in current or "PYRA" in current:
        pyro_commands.append(command)
if pyro_commands:
    body_command = pyro_commands[0]
else:
    body_command = body.AddCommandSnippet()
body_command.Name = "Pyrolyse phenolique - UserMatTh Fortran"
body_command.Input = apdl_text
body_command.Suppressed = False

# Ensure alpha and alpha_dot are written to the result file.
solver_commands = []
for candidate in ExtAPI.DataModel.GetObjectsByName("Commandes (APDL)"):
    if hasattr(candidate, "Input"):
        current = candidate.Input or ""
        if "THOPT" in current or "OUTRES,SVAR" in current:
            solver_commands.append(candidate)
if solver_commands:
    solver_command = solver_commands[0]
    solver_command.Input = "THOPT,FULL\nOUTRES,SVAR,ALL\n/GRAPHICS,FULL"
    solver_command.Suppressed = False
else:
    ExtAPI.Log.WriteWarning(
        "Le snippet de sortie SVAR n'a pas ete trouve. "
        "Conserver THOPT,FULL / OUTRES,SVAR,ALL / /GRAPHICS,FULL."
    )

# Correct a unit error visible in the generated model: 295.15 degC was
# entered although the external ambient condition is 22 degC (295.15 K).
initial_conditions = []
for child in analysis.Children:
    if hasattr(child, "InitialTemperatureValue"):
        initial_conditions.append(child)
if initial_conditions:
    initial_conditions[0].InitialTemperatureValue = Quantity("22 [C]")
else:
    ExtAPI.Log.WriteWarning("Objet Temperature initiale introuvable.")

# A lightweight Mechanical callback only stages the Fortran source and the
# environment before MAPDL starts.  The constitutive law itself is native.
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

python_objects = []
for candidate in ExtAPI.DataModel.GetObjectsByName("Code Python"):
    if hasattr(candidate, "TargetCallback") and hasattr(candidate, "Text"):
        python_objects.append(candidate)
for candidate in body.Children:
    if hasattr(candidate, "TargetCallback") and hasattr(candidate, "Text"):
        if candidate not in python_objects:
            python_objects.append(candidate)

if python_objects:
    stage_source = python_objects[0]
else:
    stage_source = body.AddPythonCodeEventBased()
stage_source.Name = "Copie UserMatTh Fortran avant solve"
stage_source.TargetCallback = PythonCodeTargetCallback.OnBeforeSolve
stage_source.Text = callback_text
stage_source.Suppressed = False
stage_source.Connect()

# Make the first native-link validation deterministic and independent of DMP.
# Once it succeeds, SMP can be returned progressively to 14 cores; the
# Fortran routine contains no mutable global variables and is thread-safe.
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
        "Configuration de solve par defaut introuvable; "
        "faire le premier test en SMP sur 1 coeur."
    )

ExtAPI.Log.WriteMessage(
    "Configuration UserMatTh Fortran terminee. "
    "Enregistrer le projet avant le solve."
)

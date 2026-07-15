"""Configure Mechanical for the prebuilt usermatthLib.dll approach.

Run with IronPython after launching Workbench through
launch_workbench_native_upf.cmd.  This version creates no Python callback.
"""

import os

from System.IO import File


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APDL_SOURCE = os.path.join(SCRIPT_DIR, "phenolic_pyrolysis_native.apdl")
DLL_SOURCE = os.path.join(SCRIPT_DIR, "usermatthLib.dll")


def first(items, description):
    if not items:
        raise RuntimeError("Objet Mechanical introuvable: " + description)
    return items[0]


if not os.path.isfile(APDL_SOURCE):
    raise RuntimeError("Commandes APDL introuvables: " + APDL_SOURCE)
if not os.path.isfile(DLL_SOURCE):
    raise RuntimeError(
        "usermatthLib.dll introuvable. Fermer Workbench et le relancer avec "
        "launch_workbench_native_upf.cmd."
    )

apdl_text = File.ReadAllText(APDL_SOURCE)
model = ExtAPI.DataModel.Project.Model
analysis = first(list(model.Analyses), "analyse Thermique transitoire")

body_candidates = []
for candidate in ExtAPI.DataModel.GetObjectsByName("phe0"):
    if (
        hasattr(candidate, "Material")
        and hasattr(candidate, "Children")
        and hasattr(candidate, "AddCommandSnippet")
    ):
        body_candidates.append(candidate)
body = first(body_candidates, "corps solide phe0")
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
body_command.Name = "Pyrolyse phenolique - UserMatTh precompile"
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

# Remove or suppress only the staging callback created by earlier revisions.
for candidate in ExtAPI.DataModel.GetObjectsByName(
    "Copie UserMatTh Fortran avant solve"
):
    if hasattr(candidate, "Suppressed"):
        candidate.Suppressed = True

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
    "Configuration usermatthLib.dll terminee. Enregistrer le projet."
)

"""Configure the copied Mechanical model for the Simulation 2 pilot."""

from System.IO import File


ROOT = r"C:\ansys_sim2"
LOG = ROOT + r"\configure_simulation2.log"
MATERIAL_APDL = ROOT + r"\phenolic_pyrolysis_outgassing.apdl"
CONTROLLER_APDL = ROOT + r"\simulation2_controller.apdl"
lines = []


def emit(text):
    lines.append(unicode(text))
    File.WriteAllText(LOG, u"\r\n".join(lines))


def get_by_id(object_id, description):
    obj = ExtAPI.DataModel.GetObjectById(object_id)
    if obj is None:
        raise RuntimeError(description + " introuvable")
    return obj


emit(u"Configuration Simulation 2")
material_text = File.ReadAllText(MATERIAL_APDL)
controller_text = File.ReadAllText(CONTROLLER_APDL)

model = ExtAPI.DataModel.Project.Model
analysis = get_by_id(104, "Analyse thermique transitoire")
settings = get_by_id(110, "Reglages de l'analyse")
body = get_by_id(32, "Corps phe0")
material_command = get_by_id(199, "Commandes materiau phe0")
controller_command = get_by_id(200, "Commandes controleur")
solution = analysis.Solution

body.Material = "PHENOLIC_PYROLYSIS"
material_command.Name = "Simulation 2 - UserMatTh et outgassing"
material_command.Input = material_text
material_command.IssueSolveCommand = True
material_command.Suppressed = False
emit(u"UserMatTh 15 proprietes / 5 SVAR insere dans phe0.")

controller_command.Name = "Simulation 2 - soufflage et ablation"
controller_command.Input = controller_text
controller_command.IssueSolveCommand = False
controller_command.Suppressed = False
emit(u"Controleur APDL insere; solve Workbench automatique desactive.")

# Preserve the validated seven-second setup displayed in Mechanical.
settings.NumberOfSteps = 1
settings.StepEndTime = Quantity("7 [sec]")
settings.InitialTimeStep = Quantity("0.05 [sec]")
settings.MinimumTimeStep = Quantity("0.001 [sec]")
settings.MaximumTimeStep = Quantity("0.05 [sec]")
emit(u"Reglages temporels confirmes: 0--7 s, macro-pas 0.05 s.")

alpha_result = get_by_id(201, "Resultat SVAR1")
existing = {}
for child in solution.Children:
    if hasattr(child, "Expression"):
        existing[str(child.Expression).upper()] = child

result_specs = (
    ("SVAR3", "Source massique de gaz"),
    ("SVAR4", "Gaz libere cumule"),
    ("SVAR5", "Puits energetique sensible des gaz"),
)
for expression, name in result_specs:
    result = existing.get(expression)
    if result is None:
        result = solution.AddUserDefinedResult()
    result.Name = name + " (" + expression + ")"
    result.Expression = expression
    result.Suppressed = False
    try:
        result.Location = alpha_result.Location
    except Exception:
        pass
    emit(u"Resultat {} configure.".format(expression))

for configuration in ExtAPI.Application.SolveConfigurations:
    process = configuration.SolveProcessSettings
    process.DistributeSolution = True
    process.MaxNumberOfCores = 10
    emit(u"{}: distribue, 10 coeurs.".format(configuration.Name))

emit(u"CONFIGURATION_SIM2_OK")
ExtAPI.Log.WriteMessage("Simulation 2 configuree et prete a lancer.")

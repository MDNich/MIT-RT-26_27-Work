"""Finalize the 0.10 degree sector model before launching Simulation 2."""

from System.IO import File
import traceback


ROOT = r"C:\ansys_sector_sim2"
LOG = ROOT + r"\configure_sector_simulation2.log"
MATERIAL_APDL = ROOT + r"\phenolic_pyrolysis_outgassing.apdl"
CONTROLLER_APDL = ROOT + r"\simulation2_controller.apdl"
lines = []


def emit(text):
    lines.append(unicode(text))
    File.WriteAllText(LOG, u"\r\n".join(lines))


def obj(object_id, description):
    result = ExtAPI.DataModel.GetObjectById(object_id)
    if result is None:
        raise RuntimeError(description + " introuvable")
    return result


def selection(ids):
    info = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    info.Ids = ids
    return info


try:
    emit("Configuration Simulation 2 - secteur 0.10 deg")
    model = ExtAPI.DataModel.Project.Model
    analysis = obj(104, "analyse thermique transitoire")
    settings = obj(110, "reglages de l'analyse")
    body = obj(213, "corps phe0_inner")
    controller = obj(200, "controleur APDL")

    # Remove orphaned contacts left by the geometry replacement.  The three
    # regenerated bonded pairs use the current face identifiers.
    for old_id in (180, 183, 186):
        old = ExtAPI.DataModel.GetObjectById(old_id)
        if old is not None:
            old.Delete()
            emit("Ancien contact {} supprime".format(old_id))

    contact_names = {
        224: "Bonded - phe0_outer to epoxy_inner",
        227: "Bonded - epoxy_outer to phe1_inner",
        230: "Bonded - phe1_outer to aluminium_inner",
    }
    for contact_id, name in contact_names.items():
        contact = obj(contact_id, "contact courant")
        contact.Name = name
        contact.Suppressed = False
        emit("{} actif".format(name))

    # The controller applies and updates the hot-side convection directly.
    # Keeping the obsolete Mechanical load would double the heat input.
    hot_convection = obj(189, "convection chaude")
    hot_convection.Location = selection([256])
    hot_convection.Suppressed = True
    emit("Convection chaude Mechanical supprimee au profit du controleur: face 256")

    outer_convection = obj(191, "convection externe")
    outer_convection.Location = selection([335])
    outer_convection.Suppressed = False
    outer_radiation = obj(193, "rayonnement externe")
    outer_radiation.Location = selection([335])
    outer_radiation.Suppressed = False
    emit("Convection et rayonnement externes affectes a la face 335")

    # Recreate the body-scoped UserMatTh command lost during geometry refresh.
    for child in list(body.Children):
        if "CommandSnippet" in child.GetType().FullName:
            child.Delete()
    material_command = body.AddCommandSnippet()
    material_command.Name = "Simulation 2 - UserMatTh phe0"
    material_command.Input = File.ReadAllText(MATERIAL_APDL)
    material_command.IssueSolveCommand = True
    material_command.Suppressed = False
    emit("UserMatTh insere sous phe0_inner")

    controller.Name = "Simulation 2 - controller sector 0.10 deg"
    controller.Input = File.ReadAllText(CONTROLLER_APDL)
    controller.IssueSolveCommand = False
    controller.Suppressed = False
    emit("Controleur sectoriel insere")

    # These result objects retained scopes from the full-ring geometry.  They
    # are not needed by the solver (the controller writes its own history) and
    # an orphaned probe can make Mechanical reject the solve before MAPDL is
    # launched.  Fresh sector results will be added after the first checkpoint.
    for result_id in (201, 202, 204, 209, 210, 211):
        result = ExtAPI.DataModel.GetObjectById(result_id)
        if result is not None:
            result.Suppressed = True
    emit("Anciens resultats et sonde a portee obsolete desactives")

    settings.NumberOfSteps = 1
    settings.StepEndTime = Quantity("7 [sec]")
    settings.InitialTimeStep = Quantity("0.05 [sec]")
    settings.MinimumTimeStep = Quantity("0.001 [sec]")
    settings.MaximumTimeStep = Quantity("0.05 [sec]")

    for configuration in ExtAPI.Application.SolveConfigurations:
        process = configuration.SolveProcessSettings
        process.DistributeSolution = True
        process.MaxNumberOfCores = 10
    emit("Calcul distribue configure sur 10 rangs")

    # Final hard guards before saving the project.
    current_contacts = list(ExtAPI.DataModel.GetObjectsByType(DataModelObjectCategory.ContactRegion))
    if len(current_contacts) != 3:
        raise RuntimeError("Nombre de contacts inattendu: {}".format(len(current_contacts)))
    if body.Material != "PHENOLIC_PYROLYSIS":
        raise RuntimeError("Materiau phe0 incorrect: {}".format(body.Material))
    mesh_data = analysis.MeshData
    if mesh_data.Nodes.Count != 54540 or mesh_data.Elements.Count != 35200:
        raise RuntimeError("Le maillage valide n'est plus present: {} noeuds, {} elements".format(
            mesh_data.Nodes.Count, mesh_data.Elements.Count))

    emit("CONFIGURATION_SECTOR_SIM2_OK")
    ExtAPI.Log.WriteMessage("Simulation 2 sectorielle configuree et verifiee.")
except Exception:
    emit("CONFIGURATION_SECTOR_SIM2_FAILED")
    emit(traceback.format_exc())
    raise

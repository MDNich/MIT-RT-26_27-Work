"""Launch the configured sector solve from Mechanical."""

from System import DateTime
from System.IO import File
import traceback


ROOT = r"C:\ansys_sector_sim2"
LOG = ROOT + r"\launch_sector_simulation2.log"
lines = []


def emit(text):
    lines.append(unicode(text))
    File.WriteAllText(LOG, u"\r\n".join(lines))


try:
    emit("LAUNCH_REQUESTED_UTC={}".format(DateTime.UtcNow.ToString("o")))
    configuration = File.ReadAllText(ROOT + r"\configure_sector_simulation2.log")
    if "CONFIGURATION_SECTOR_SIM2_OK" not in configuration:
        raise RuntimeError("Configuration finale non validee")

    analysis = ExtAPI.DataModel.Project.Model.Analyses[0]
    mesh_data = analysis.MeshData
    if mesh_data.Nodes.Count != 54540 or mesh_data.Elements.Count != 35200:
        raise RuntimeError("Maillage inattendu au lancement")

    # Remove only stale generated solution data in the copied project.  The
    # current geometry, materials, contacts, mesh and loads are preserved.
    analysis.Solution.ClearGeneratedData()
    emit("SOLVE_STARTED_UTC={}".format(DateTime.UtcNow.ToString("o")))
    emit("NODES={} ELEMENTS={} DMP_RANKS=10".format(
        mesh_data.Nodes.Count, mesh_data.Elements.Count))
    ExtAPI.Log.WriteMessage("Simulation 2 sectorielle: lancement du solveur.")
    configurations = list(ExtAPI.Application.SolveConfigurations)
    configuration = [item for item in configurations if item.Default][0]
    emit("SOLVE_CONFIGURATION={}".format(configuration.Name))
    analysis.Solution.Solve(True, configuration)
    emit("SOLVE_RETURNED_UTC={}".format(DateTime.UtcNow.ToString("o")))
    emit("SOLVE_STATUS={}".format(analysis.Solution.Status))
    emit("SOLVE_STATE={}".format(analysis.Solution.State))
    try:
        for message in ExtAPI.Application.Messages:
            emit("MESSAGE {} | {}".format(message.Severity, message.DisplayString))
    except Exception:
        emit("MESSAGE_DUMP_FAILED")
        emit(traceback.format_exc())
    try:
        info = ExtAPI.DataModel.GetObjectById(106)
        emit("SOLVER_OUTPUT_BEGIN")
        emit(info.SolverOutput)
        emit("SOLVER_OUTPUT_END")
    except Exception:
        emit("SOLVER_OUTPUT_UNAVAILABLE")
except Exception:
    emit("LAUNCH_OR_SOLVE_FAILED")
    emit(traceback.format_exc())
    raise

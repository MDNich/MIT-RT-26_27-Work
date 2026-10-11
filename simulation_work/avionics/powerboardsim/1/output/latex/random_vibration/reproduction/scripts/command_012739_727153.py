from Ansys.Mechanical.DataModel.Enums import ContactBehavior,ContactFormulation,ContactDetectionPoint,ElementOrder
from Ansys.ACT.Interfaces.Common import SelectionTypeEnum
from Ansys.Core.Units import Quantity
def sel(ids):
 s=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities);s.Ids=ids;return s
with Transaction():
 m.Mesh.ElementOrder=ElementOrder.Quadratic
 for name,ids,size in [('PCB - 0.7 mm',[42342],0.7),('Six bolts - 0.4 mm',[21279,21629,21979,22329,22679,23029],0.4)]:
  z=m.Mesh.AddSizing();z.Name=name;z.Location=sel(ids);z.ElementSize=Quantity(str(size)+' [mm]')
 for line in System.IO.File.ReadAllLines(PCB670_RUN+r'\bolted750_asymmetric\contact_changes.tsv'):
  o=ExtAPI.DataModel.GetObjectById(int(line.split('\t')[0]));o.Behavior=ContactBehavior.Asymmetric;o.ContactFormulation=ContactFormulation.MPC;o.DetectionMethod=ContactDetectionPoint.NodalNormalToTarget
System.IO.File.WriteAllText(PCB670_RUN+r'\MESH_REFINEMENT_STARTED.txt',System.DateTime.UtcNow.ToString('o'))
m.Mesh.GenerateMesh()
System.IO.File.WriteAllText(PCB670_RUN+r'\MESH_REFINEMENT_RETURNED.txt',str(m.Mesh.ObjectState)+'\nNodes='+str(m.Mesh.Nodes)+'\nElements='+str(m.Mesh.Elements))

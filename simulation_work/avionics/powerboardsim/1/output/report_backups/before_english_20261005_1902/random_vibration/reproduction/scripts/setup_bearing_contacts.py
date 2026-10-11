# Six compression-bearing seats for the explicit bolt-clamped case.
# Assumption: metal washer faces seat against the PCB underside when tightened.
import System
from Ansys.Core.Units import Quantity
from Ansys.ACT.Interfaces.Common import SelectionTypeEnum
from Ansys.Mechanical.DataModel.Enums import ContactType,ContactBehavior,ContactFormulation
case=PCB670_RUN+r'\bolted750_refined';System.IO.Directory.CreateDirectory(case)
def sel(ids):
 s=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities);s.Ids=ids;return s
def enumset(o,name,value):
 p=o.GetType().GetProperty(name);p.SetValue(o,System.Enum.Parse(p.PropertyType,value),None)
assert System.IO.File.Exists(PCB670_RUN+r'\default_refined\RESULTS_VERIFIED.txt')
log=[]
with Transaction():
 for o in list(manager.Children):o.Suppressed=False
 # Replace four incidental washer/standoff bonds with a consistent bearing model.
 for oid in [1696,1732,1744,1771]:
  o=ExtAPI.DataModel.GetObjectById(oid);log.append('SUPPRESS '+str(oid)+' '+o.Name);o.Suppressed=True
 for i,gid in enumerate([20246,20040,20525,20466,20878,20407]):
  b=ExtAPI.DataModel.GeoData.GeoEntityById(gid)
  faces=[f for f in b.Faces if str(f.SurfaceType)=='GeoSurfacePlane' and f.Area>70 and abs(list(f.Centroid)[2]+1.2971797)<0.001]
  assert len(faces)==1,str(gid)
  name='PCB750 bearing seat %02d - metal washer to PCB'%(i+1)
  found=[o for o in m.Connections.GetChildren(DataModelObjectCategory.ContactRegion,True) if o.Name==name]
  c=found[0] if found else m.Connections.AddContactRegion();c.Name=name
  c.SourceLocation=sel([faces[0].Id]);c.TargetLocation=sel([41909]);c.ContactType=ContactType.Frictionless
  c.Behavior=ContactBehavior.Asymmetric;c.ContactFormulation=ContactFormulation.AugmentedLagrange
  enumset(c,'PinballRegion','Radius');c.PinballRadius=Quantity('1 [mm]')
  enumset(c,'InterfaceTreatment','AdjustToTouch')
  log.append('SEAT '+str(i+1)+' contact='+str(c.ObjectId)+' washer_body='+str(gid)+' face='+str(faces[0].Id)+' target=41909 gap_mm=0.7459997')
 a=static.AnalysisSettings
 enumset(a,'WeakSprings','Off')
 a.LargeDeflection=True
 for step in [1,2]:
  a.CurrentStepNumber=step;enumset(a,'AutomaticTimeStepping','On');a.InitialSubsteps=5;a.MinimumSubsteps=1;a.MaximumSubsteps=100
System.IO.File.WriteAllText(case+r'\bearing_model.txt','\n'.join(log))
bm.StartApdlInputFileWrite(static);static.WriteInputFile(case+r'\static_input.dat')
System.IO.File.WriteAllText(case+r'\SETUP_READY.txt','750 N per bolt; step 1 preload, step 2 locked. Six frictionless metal washer/PCB seats, adjust initial CAD gap. No cell-to-PCB connection. Refined common mesh, full integration, no weak springs.')

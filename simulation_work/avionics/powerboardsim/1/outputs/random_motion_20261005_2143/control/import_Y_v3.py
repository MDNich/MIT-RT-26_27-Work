import System
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
try:
 a=ExtAPI.DataModel.Project.Model.AddTransientStructuralAnalysis();a.Name='Transient motion - base Y'
 a.AnalysisSettings.StepEndTime=Quantity(9,'s');a.AnalysisSettings.TimeStep=Quantity(1.0/65536,'s')
 a.InitialConditions[0].ModalEnvironmentTransientMSUPIC=ExtAPI.DataModel.GetObjectById(4254)
 a.Solution.ReadGivenAnsysResultFileByReference(r'C:\Temp\PBMotion_20261005_expand_Y\file.rst',UnitSystemIDType.UnitsMKS)
 reader=a.GetResultsData();times=list(reader.ListTimeFreq);assert len(times)==480
 ns=[44,2064,2075,2185,42154,42242,136765];rows=['set,time,node,ux,uy,uz']
 for i in [1,2,120,240,360,480]:
  reader.CurrentResultSet=i;u=reader.GetResult('U')
  for n in ns:
   v=list(u.GetNodeValues(n));rows.append('%d,%.16g,%d,%.16g,%.16g,%.16g'%(i,times[i-1],n,v[0],v[1],v[2]))
 reader.Dispose()
 System.IO.File.WriteAllLines(pbmotionroot+r'\expand_Y\native_node_checks.csv',rows)
 System.IO.File.WriteAllLines(pbmotionroot+r'\expand_Y\times.txt',['%.17g'%t for t in times])
 ids=[]
 for idx,axis in enumerate('XYZ'):
  r=a.Solution.AddDirectionalDeformation();r.Name='Instantaneous displacement '+axis+' - base Y'
  p=r.GetType().GetProperty('NormalOrientation');p.SetValue(r,System.Enum.Parse(p.PropertyType,axis+'Axis'),None)
  p=r.GetType().GetProperty('By');p.SetValue(r,System.Enum.Parse(p.PropertyType,'ResultSet'),None)
  r.SetNumber=1;r.CalculateTimeHistory=(axis=="Z");r.EvaluateAllResults();ids.append(str(r.ObjectId))

 r=a.Solution.AddDirectionalDeformation();r.Name='Instantaneous PCB displacement Z - base Y'
 p=r.GetType().GetProperty('NormalOrientation');p.SetValue(r,System.Enum.Parse(p.PropertyType,'ZAxis'),None)
 p=r.GetType().GetProperty('By');p.SetValue(r,System.Enum.Parse(p.PropertyType,'ResultSet'),None)
 sel=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities);sel.Ids=[42342];r.Location=sel
 r.SetNumber=1;r.CalculateTimeHistory=True;r.EvaluateAllResults();ids.append(str(r.ObjectId))
 System.IO.File.WriteAllText(pbmotionroot+r'\expand_Y\result_ids.txt',','.join(ids))
 System.IO.File.WriteAllText(pbmotionroot+r'\expand_Y\IMPORTED.txt',str(a.ObjectId))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

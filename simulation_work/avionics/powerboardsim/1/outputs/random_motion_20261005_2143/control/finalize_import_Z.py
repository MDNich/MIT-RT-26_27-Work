import System
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
try:
 branch=pbmotionroot+r'\expand_Z';a=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(branch+r'\IMPORTED.txt')))
 reader=a.GetResultsData();times=list(reader.ListTimeFreq);reader.Dispose()
 System.IO.File.WriteAllLines(branch+r'\times.txt',['%.17g'%t for t in times])
 ids=System.IO.File.ReadAllText(branch+r'\result_ids.txt').split(',')
 if len(ids)==3:
  r=a.Solution.AddDirectionalDeformation();r.Name='Instantaneous PCB displacement Z - base Z'
  p=r.GetType().GetProperty('NormalOrientation');p.SetValue(r,System.Enum.Parse(p.PropertyType,'ZAxis'),None)
  p=r.GetType().GetProperty('By');p.SetValue(r,System.Enum.Parse(p.PropertyType,'ResultSet'),None)
  sel=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities);sel.Ids=[42342];r.Location=sel
  r.SetNumber=1;r.CalculateTimeHistory=True;r.EvaluateAllResults();ids.append(str(r.ObjectId))
  System.IO.File.WriteAllText(branch+r'\result_ids.txt',','.join(ids))
 ExtAPI.DataModel.Project.Save()
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

import System
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
try:
 for axis in 'XYZ':
  branch=pbmotionroot+'\\expand_'+axis
  a=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(branch+r'\IMPORTED.txt')))
  ids=System.IO.File.ReadAllText(branch+r'\result_ids.txt').split(',')
  if len(ids)==3:
   r=a.Solution.AddDirectionalDeformation();r.Name='Instantaneous PCB displacement Z - base '+axis
   p=r.GetType().GetProperty('NormalOrientation');p.SetValue(r,System.Enum.Parse(p.PropertyType,'ZAxis'),None)
   p=r.GetType().GetProperty('By');p.SetValue(r,System.Enum.Parse(p.PropertyType,'ResultSet'),None)
   sel=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities);sel.Ids=[42342];r.Location=sel
   r.SetNumber=1;r.CalculateTimeHistory=True;r.EvaluateAllResults();ids.append(str(r.ObjectId))
   System.IO.File.WriteAllText(branch+r'\result_ids.txt',','.join(ids))
 System.IO.File.WriteAllText(pbmotionroot+r'\control\VIDEO_RESULTS_READY.txt',System.DateTime.UtcNow.ToString('o'))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

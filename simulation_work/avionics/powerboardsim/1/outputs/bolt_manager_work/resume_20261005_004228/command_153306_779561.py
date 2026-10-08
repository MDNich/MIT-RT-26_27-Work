md=ExtAPI.DataModel.MeshDataByName('Global')
ls=[]
for b in Model.Geometry.GetChildren(DataModelObjectCategory.Body,True):
 try:
  reg=md.MeshRegionById(b.GetGeoBody().Id)
  if 7017 in list(reg.ElementIds):ls.append('Peak assembly X stress body: '+unicode(b.Name)+' geometry '+unicode(b.GetGeoBody().Id))
 except:pass
System.IO.File.WriteAllText(RV_ROOT+r'\X\stress_hotspot_body.txt','\n'.join(ls))
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')
ExtAPI.Application.LicensePreference.DeActivateLicense()
System.IO.File.WriteAllText(RV_ROOT+r'\mechanical_license_released.txt',System.DateTime.UtcNow.ToString('o'))

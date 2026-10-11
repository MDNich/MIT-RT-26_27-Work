pbr=ExtAPI.DataModel.GetObjectById(4566)
pbl=[str(pbr.ObjectState),str(pbr.Location),str(pbr.Maximum)]
for pbp in pbr.GetType().GetProperties():
 if any(s in pbp.Name.lower() for s in ['time','set','by','scope','location','result','suppres','maximum']):
  try:pbl.append(str(pbp.Name)+'='+str(pbp.GetValue(pbr,None)))
  except:pass
System.IO.File.WriteAllLines(pbmotionroot+r'\pilot_expand_nodal\result_properties.txt',pbl)
ExtAPI.Application.LicensePreference.DeActivateLicense()

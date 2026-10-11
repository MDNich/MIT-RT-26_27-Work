pbl=[]
for pbi in [4559,4560,4566,4567]:
 pbo=ExtAPI.DataModel.GetObjectById(pbi);pbl.append(str(pbi)+' '+unicode(pbo.ObjectState))
 if hasattr(pbo,'Maximum'):pbl.append(unicode(pbo.Maximum))
for pbm in ExtAPI.Application.Messages:pbl.append(unicode(pbm.DisplayString))
System.IO.File.WriteAllLines(pbmotionroot+r'\pilot_expand_nodal\held_license_check.txt',pbl)
ExtAPI.Application.LicensePreference.DeActivateLicense()

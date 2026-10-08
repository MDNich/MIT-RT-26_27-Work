pblp=ExtAPI.Application.LicensePreference
pbl=[str(x) for x in pblp.GetType().GetMethods()]
for pbp in pblp.GetType().GetProperties():
 try:pbl.append(str(pbp.Name)+'='+str(pbp.GetValue(pblp,None)))
 except:pass
System.IO.File.WriteAllLines(pbmotionroot+r'\control\license_api.txt',pbl)

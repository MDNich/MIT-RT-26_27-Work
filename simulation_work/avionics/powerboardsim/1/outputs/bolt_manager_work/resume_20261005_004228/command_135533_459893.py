s=[]
o=ExtAPI.Application.LicensePreference
s.append(unicode(o.GetType().FullName))
for p in o.GetType().GetProperties():
 try:s.append('%s|%s|%s'%(p.Name,p.PropertyType.FullName,p.GetValue(o,None)))
 except:pass
for m in o.GetType().GetMethods():s.append(unicode(m))
System.IO.File.WriteAllText(RV_ROOT+r'\license_api.txt','\n'.join(s))

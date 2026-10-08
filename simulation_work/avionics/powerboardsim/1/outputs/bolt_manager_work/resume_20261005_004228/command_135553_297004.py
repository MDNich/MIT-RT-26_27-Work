lic=ExtAPI.Application.LicensePreference
System.IO.File.WriteAllText(RV_ROOT+r'\license_before.txt','\n'.join(unicode(n)+'|'+unicode(lic.GetLicenseStatus(n)) for n in lic.GetAllLicenses()))
lic.ActivateLicense('Ansys Mechanical Enterprise')
System.IO.File.WriteAllText(RV_ROOT+r'\license_reactivated.txt',System.DateTime.UtcNow.ToString('o')+'\n'+unicode(rvmodal.ObjectState))

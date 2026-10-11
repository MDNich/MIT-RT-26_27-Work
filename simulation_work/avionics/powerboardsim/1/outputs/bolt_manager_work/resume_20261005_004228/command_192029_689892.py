import System
rr=ExtAPI.Application.LicensePreference.DeActivateLicense()
System.IO.File.WriteAllText(PULLROOT+r'\audit\post_license_released.txt',str(rr)+' '+System.DateTime.UtcNow.ToString('o'))

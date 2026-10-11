import System
ExtAPI.Application.LicensePreference.DeActivateLicense()
System.IO.File.WriteAllText(r'C:\Temp\PBMotionControl\FINAL_VIDEOS_LICENSE_RELEASED.txt',System.DateTime.UtcNow.ToString('o'))

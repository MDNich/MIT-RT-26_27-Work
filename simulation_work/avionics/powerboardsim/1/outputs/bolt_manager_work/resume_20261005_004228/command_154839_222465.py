assert unicode(rvs[1].Solution.ObjectState)=='Solved'
ExtAPI.Application.LicensePreference.DeActivateLicense()
System.IO.File.WriteAllText(System.IO.Path.Combine(RV_ROOT,'license_released_before_Z.txt'),System.DateTime.UtcNow.ToString('o'))

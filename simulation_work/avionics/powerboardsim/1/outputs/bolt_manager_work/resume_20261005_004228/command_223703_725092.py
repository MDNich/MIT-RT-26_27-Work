pblp=ExtAPI.Application.LicensePreference
System.IO.File.WriteAllLines(pbmotionroot+r'\control\license_choices.txt',[str(x)+' '+str(pblp.GetLicenseStatus(x)) for x in pblp.GetAllLicenses()])

import System
rows=[]
for a in ExtAPI.DataModel.Project.Model.Analyses:
 rows.append(unicode(a.ObjectId)+' | '+unicode(a.Name)+' | '+unicode(a.AnalysisType))
System.IO.File.WriteAllLines(pbmotionroot+r'\control\recovered_analyses.txt',rows)
ExtAPI.Application.LicensePreference.DeActivateLicense()

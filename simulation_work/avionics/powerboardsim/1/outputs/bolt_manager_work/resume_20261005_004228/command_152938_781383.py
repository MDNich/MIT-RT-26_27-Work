ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
a=rvs[0]
path=r'C:\Temp\PCBRV_20261005_X_local_v2\file.rst'
assert System.IO.File.Exists(RV_ROOT+r'\X\local_recovery_v2\NATIVE_SOLVED.txt')
assert System.IO.File.Exists(RV_ROOT+r'\X\local_recovery_v2\file.rst')
a.Solution.ReadGivenAnsysResultFileByReference(path,Ansys.Mechanical.DataModel.Enums.UnitSystemIDType.UnitsMKS)
ls=['Linked '+unicode(a.Solution.ObjectState),unicode(a.Solution.ResultFilePath)]
r=ExtAPI.DataModel.GetObjectById(4278)
try:
 r.EvaluateAllResults()
 ls.append('Single result evaluated '+unicode(r.ObjectState)+' '+unicode(r.Maximum))
except Exception as exc:ls.append('Single result error '+unicode(exc))
ls.append('Native file exists '+unicode(System.IO.File.Exists(path)))
System.IO.File.WriteAllText(RV_ROOT+r'\X\external_import.txt','\n'.join(ls))

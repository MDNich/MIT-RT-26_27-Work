a=rvs[0]
ls=[]
for name in ['rd','reader']:
 try:
  obj=globals().get(name)
  if obj is not None:obj.Dispose();ls.append('Disposed '+name)
 except Exception as exc:ls.append('Dispose '+name+' '+unicode(exc))
try:
 a.Solution.ReadGivenAnsysResultFileByReference(System.IO.Path.Combine(a.WorkingDir,'file.rst'),Ansys.Mechanical.DataModel.Enums.UnitSystemIDType.UnitsMKS)
 ls.append('Imported '+unicode(a.Solution.ObjectState)+' '+unicode(a.Solution.Status))
except Exception as exc:ls.append('Import error '+unicode(exc))
System.IO.File.WriteAllText(RV_ROOT+r'\X\import_probe.txt','\n'.join(ls))

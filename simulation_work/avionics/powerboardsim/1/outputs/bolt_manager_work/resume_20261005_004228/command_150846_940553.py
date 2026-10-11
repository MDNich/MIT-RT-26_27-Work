ls=[]
a=rvs[0]
ls.append('unit enum '+','.join(System.Enum.GetNames(Ansys.Mechanical.DataModel.Enums.UnitSystemIDType)))
for target in [a.Solution]:
 for p in target.GetType().GetProperties():
  if any(x in p.Name.lower() for x in ['resultfile','unit']):
   try:ls.append(p.Name+'|'+unicode(p.GetValue(target,None)))
   except:pass
try:
 a.Solution.ReloadResultFile()
 ls.append('Reloaded '+unicode(a.Solution.ObjectState))
except Exception as exc:ls.append('Reload error '+unicode(exc))
System.IO.File.WriteAllText(RV_ROOT+r'\X\reload_probe.txt','\n'.join(ls))

a=rvs[0]
ls=[]
try:
 a.Solution.EvaluateAllResults()
 ls.append('Evaluated '+unicode(a.Solution.ObjectState)+' '+unicode(a.Solution.Status))
except Exception as exc:ls.append('Evaluate error '+unicode(exc))
for o in a.Solution.Children:
 if hasattr(o,'Maximum'):ls.append('%s|%s|%s|%s'%(o.ObjectId,o.Name,o.ObjectState,o.Maximum))
System.IO.File.WriteAllText(RV_ROOT+r'\X\evaluate_probe.txt','\n'.join(ls))

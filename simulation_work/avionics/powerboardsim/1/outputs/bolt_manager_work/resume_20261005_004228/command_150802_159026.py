a=rvs[0]
ls=[]
for target in [a,a.Solution]:
 ls.append('TYPE '+unicode(target.GetType()))
 for m in target.GetType().GetMethods():
  if any(s in m.Name.lower() for s in ['read','result','status','evaluate']):ls.append(unicode(m))
try:
 rd=a.GetResultsData()
 ls.append('RESULTS '+unicode(list(rd.ListTimeFreq)))
except Exception as exc:ls.append('READER ERROR '+unicode(exc))
System.IO.File.WriteAllText(RV_ROOT+r'\X\result_reader_probe.txt','\n'.join(ls))

ls=[]
for m in ExtAPI.Application.Messages:
 ls.append(unicode(m.Severity)+'|'+unicode(m.DisplayString))
ls.append('X status '+unicode(rvs[0].Solution.ObjectState)+' '+unicode(rvs[0].Solution.Status))
for o in rvs[0].Solution.Children:ls.append(str(o.ObjectId)+'|'+unicode(o.Name)+'|'+unicode(o.ObjectState))
System.IO.File.WriteAllText(RV_ROOT+r'\X\mechanical_messages.txt','\n'.join(ls))

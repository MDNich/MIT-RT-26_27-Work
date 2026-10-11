o=list(manager.Children)[0]
lines=[]
for target in [o,o.InternalObject,o.Controller.GetMechanicalObj().InternalObject]:
 lines.append(unicode(target.GetType()))
 for p in target.GetType().GetProperties():
  if any(x in p.Name.lower() for x in ['suppress','active','state','analysis']):
   try:lines.append(p.Name+'='+unicode(p.GetValue(target,None)))
   except:pass
 for method in target.GetType().GetMethods():
  if 'suppres' in method.Name.lower():lines.append(unicode(method))
System.IO.File.WriteAllText(PCB670_RUN+r'\suppress_api.txt',u'\n'.join(lines))

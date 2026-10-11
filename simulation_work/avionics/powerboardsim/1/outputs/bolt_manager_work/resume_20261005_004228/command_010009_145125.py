ls=[]
for target in [ExtAPI.Graphics,ExtAPI.Graphics.Camera,list(baseline.Solution.Children)[-1]]:
 ls.append(unicode(target.GetType()))
 ls.extend(unicode(m) for m in target.GetType().GetMethods() if any(t in m.Name.lower() for t in ['export','fit','orient','scale']))
 ls.extend(unicode(p) for p in target.GetType().GetProperties() if any(t in p.Name.lower() for t in ['mode','scale','result']))
System.IO.File.WriteAllText(PCB670_RUN+r'\result_api.txt',u'\n'.join(ls))

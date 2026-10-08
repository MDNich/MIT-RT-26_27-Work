import System
reader=baseline.GetResultsData();fs=list(reader.ListTimeFreq);reader.Dispose()
System.IO.File.WriteAllText(PCB670_RUN+r'\default\initial_frequencies.txt',unicode(fs))
System.IO.Directory.CreateDirectory(PCB670_RUN+r'\default\initial_attempt')
for name in ['ds.dat','solve.out','file.rst','file0.err']:
 p=System.IO.Path.Combine(baseline.WorkingDir,name)
 if System.IO.File.Exists(p):System.IO.File.Copy(p,PCB670_RUN+r'\default\initial_attempt\'+name,True)
ls=[]
for target in [ExtAPI.Graphics,ExtAPI.Graphics.Camera,list(baseline.Solution.Children)[-1]]:
 ls.append(unicode(target.GetType()))
 ls.extend(unicode(m) for m in target.GetType().GetMethods() if any(t in m.Name.lower() for t in ['export','fit','orient','scale']))
 ls.extend(unicode(p) for p in target.GetType().GetProperties() if any(t in p.Name.lower() for t in ['mode','scale','result']))
System.IO.File.WriteAllText(PCB670_RUN+r'\result_api.txt',u'\n'.join(ls))

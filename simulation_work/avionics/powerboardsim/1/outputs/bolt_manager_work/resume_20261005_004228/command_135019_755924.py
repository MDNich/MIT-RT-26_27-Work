import System
RV_ROOT=System.IO.Path.GetDirectoryName(System.IO.Path.GetDirectoryName(PCB670_RUN))+r'\random_vibration_20261005_0950'
System.IO.Directory.CreateDirectory(RV_ROOT)
s=[]
s.append('UTC '+System.DateTime.UtcNow.ToString('o'))
for a in list(ExtAPI.DataModel.Project.Model.Analyses):
 s.append('ANALYSIS %s %s %s %s'%(a.ObjectId,a.Name,a.AnalysisType,a.Solution.ObjectState))
 s.append('DIR '+unicode(a.WorkingDir))
 for ch in list(a.Children):
  s.append(' CHILD %s %s %s'%(ch.ObjectId,ch.Name,ch.DataModelObjectCategory))
for o in [ExtAPI.DataModel.GetObjectById(1656),ExtAPI.DataModel.GetObjectById(1656).AnalysisSettings,ExtAPI.DataModel.GetObjectById(1659)]:
 s.append('OBJECT '+unicode(o.Name))
 for p in o.GetType().GetProperties():
  if any(k in p.Name.lower() for k in ['modal','mode','frequ','mass','upstream','source','pre','damp','stress','link','expan','retain']):
   try:s.append('%s|%s|%s'%(p.Name,p.PropertyType.FullName,p.GetValue(o,None)))
   except Exception as e:s.append(p.Name+' ERR '+unicode(e))
 s.append('METHODS '+';'.join(unicode(m) for m in o.GetType().GetMethods() if any(k in m.Name.lower() for k in ['duplicate','clone','upstream','link','pre','transf'])))
System.IO.File.WriteAllText(RV_ROOT+r'\initial_probe.txt','\n'.join(s))

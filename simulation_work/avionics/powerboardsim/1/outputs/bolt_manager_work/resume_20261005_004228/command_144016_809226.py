ls=[]
for target in [ExtAPI.DataModel.GetObjectById(4274),rvs[0].AnalysisSettings,Model]:
 ls.append('TYPE '+unicode(target.GetType()))
 for p in target.GetType().GetProperties():
  if any(s in p.Name.lower() for s in ['grav','accel','psd']):
   try:ls.append(p.Name+'|'+unicode(p.PropertyType)+'|'+unicode(p.GetValue(target,None))+'|write='+unicode(p.CanWrite))
   except:pass
ls.append('ADD '+str(hasattr(rvs[0],'AddPSDAcceleration')))
System.IO.File.WriteAllText(RV_ROOT+r'\gravity_probe.txt','\n'.join(ls))

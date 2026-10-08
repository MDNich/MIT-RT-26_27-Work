s=[]
for o,names in [(rvs[0].AnalysisSettings,['ConstantDamping','ModeSelectionMethod']),(load,['Direction'])]:
 for n in names:
  p=o.GetType().GetProperty(n);s.append(n+' ENUM '+','.join(System.Enum.GetNames(p.PropertyType)))
for p in load.Properties:
 s.append('PROP '+unicode(p.Name)+' '+unicode(p.APIName))
 for q in p.GetType().GetProperties():
  if any(k in q.Name.lower() for k in ['value','valid','option','name','read']):
   try:s.append(q.Name+'='+unicode(q.GetValue(p,None)))
   except:pass
for a in [rvmodal]+rvs:
 s.append('ANALYSIS '+unicode(a.ObjectId)+' '+unicode(a.Name))
 for ic in [x for x in a.Children if unicode(x.DataModelObjectCategory)=='InitialCondition']:
  s.append('IC '+unicode(ic.ObjectId)+' parentstatic '+unicode(ic.PreStressICEnvironment)+' parentmodal '+unicode(ic.ModalEnvironmentPSDIC))
System.IO.File.WriteAllText(RV_ROOT+r'\load_options.txt','\n'.join(s))

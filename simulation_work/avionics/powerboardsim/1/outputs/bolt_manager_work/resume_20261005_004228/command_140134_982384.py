ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
rvs=[ExtAPI.DataModel.GetObjectById(int(x)) for x in System.IO.File.ReadAllLines(RV_ROOT+r'\new_random_ids.txt')]
s=[]
for a,axis in zip(rvs,['X','Y','Z']):
 a.Name='RANDOM VIBE - '+axis+' - 2pct damping'
 ic=[x for x in list(a.Children) if unicode(x.DataModelObjectCategory)=='InitialCondition'][0]
 ic.ModalEnvironmentPSDIC=rvmodal
 load=a.AddPSDGAcceleration()
 load.Name='Base acceleration PSD - '+axis
 s.append('ANALYSIS '+unicode(a.ObjectId)+' LOAD '+unicode(load.ObjectId)+' STATE '+unicode(a.ObjectState))
for o in [rvmodal.AnalysisSettings,rvs[0].AnalysisSettings,load,load.LoadData]:
 s.append('OBJECT '+unicode(o.GetType().FullName))
 for p in o.GetType().GetProperties():
  if p.Name in ['Children','Properties','VisibleProperties','Parent','InternalObject','ObjectTags']:continue
  try:s.append('%s|%s|%s'%(p.Name,p.PropertyType.FullName,p.GetValue(o,None)))
  except:pass
System.IO.File.WriteAllText(RV_ROOT+r'\setup_probe.txt','\n'.join(s))

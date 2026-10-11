rvmodel=ExtAPI.DataModel.Project.Model
rvmodal=rvmodel.AddModalAnalysis()
rvmodal.Name='RANDOM VIBE - expanded prestressed modal basis'
System.IO.File.WriteAllText(RV_ROOT+r'\new_modal_id.txt',unicode(rvmodal.ObjectId))
rvic=[x for x in list(rvmodal.Children) if unicode(x.DataModelObjectCategory)=='InitialCondition'][0]
rvic.PreStressICEnvironment=ExtAPI.DataModel.GetObjectById(4123)
ms=rvmodal.AnalysisSettings
orig=ExtAPI.DataModel.GetObjectById(1656).AnalysisSettings
orig.CopyTo(ms)
ms.MaximumModesToFind=60
ms.LimitSearchToRange=True
ms.SearchRangeMinimum=Quantity('1 [Hz]')
ms.SearchRangeMaximum=Quantity('4000 [Hz]')
ms.Damped=False
ms.Stress=True
ms.Strain=True
ms.NodalForces=True
rvs=[]
for axis in ['X','Y','Z']:
 a=rvmodel.AddRandomVibrationAnalysis()
 a.Name='RANDOM VIBE - '+axis+' - 20 to 2000 Hz'
 ic=[x for x in list(a.Children) if unicode(x.DataModelObjectCategory)=='InitialCondition'][0]
 ic.ModalEnvironmentPSDIC=rvmodal
 load=a.AddPSDGAcceleration()
 load.Name='Base acceleration PSD - '+axis
 rvs.append(a)
System.IO.File.WriteAllText(RV_ROOT+r'\new_random_ids.txt','\n'.join(unicode(a.ObjectId) for a in rvs))
s=[]
for o in [ms,rvs[0].AnalysisSettings,rvs[0].Children[0],load,load.LoadData]:
 s.append('OBJECT '+unicode(o.GetType().FullName))
 for p in o.GetType().GetProperties():
  try:s.append('%s|%s|%s'%(p.Name,p.PropertyType.FullName,p.GetValue(o,None)))
  except:pass
System.IO.File.WriteAllText(RV_ROOT+r'\setup_probe.txt','\n'.join(s))

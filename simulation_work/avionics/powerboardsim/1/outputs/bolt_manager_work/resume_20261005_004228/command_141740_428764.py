rvresults=[]
for a,axis in zip(rvs,['X','Y','Z']):
 for comp in ['X','Y','Z']:
  d=a.Solution.AddDirectionalDeformation();d.Name='RMS displacement '+comp+' - base '+axis
  rv_enum(d,'NormalOrientation',comp+'Axis');rvresults.append(d)
  q=a.Solution.AddDirectionalAcceleration();q.Name='RMS absolute acceleration '+comp+' - base '+axis
  rv_enum(q,'NormalOrientation',comp+'Axis');rvresults.append(q)
 eqa=a.Solution.AddEquivalentStress();eqa.Name='RMS equivalent stress - all bodies';rvresults.append(eqa)
 eqp=a.Solution.AddEquivalentStress();eqp.Name='RMS equivalent stress - PCB'
 sel=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities);sel.Ids=[42342];eqp.Location=sel;rvresults.append(eqp)
s=[]
for o in [rvresults[0],rvresults[1],rvresults[-1]]:
 s.append('OBJECT '+unicode(o.GetType().FullName))
 for p in o.GetType().GetProperties():
  if any(k in p.Name.lower() for k in ['orientation','factor','aver','scale','max','minimum','unit','location','scope','acceleration','display']):
   try:s.append('%s|%s|%s'%(p.Name,p.PropertyType.FullName,p.GetValue(o,None)))
   except:pass
System.IO.File.WriteAllText(RV_ROOT+r'\result_probe.txt','\n'.join(s))
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')

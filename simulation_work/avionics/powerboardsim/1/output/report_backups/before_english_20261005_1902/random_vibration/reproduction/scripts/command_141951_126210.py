# Remove only incompatible, newly-created, unevaluated result placeholders.
for a in rvs:
 for ch in list(a.Solution.Children):
  if unicode(ch.DataModelObjectCategory) in ['DirectionalAcceleration','EquivalentStress']:ch.Delete()
rvresults=[]
for a,axis in zip(rvs,['X','Y','Z']):
 for comp in ['X','Y','Z']:
  name='RMS displacement '+comp+' - base '+axis
  existing=[x for x in a.Solution.Children if unicode(x.Name)==name]
  d=existing[0] if existing else a.Solution.AddDirectionalDeformation()
  d.Name=name;rv_enum(d,'NormalOrientation',comp+'Axis');rvresults.append(d)
  q=a.Solution.AddDirectionalAccelerationPSD();q.Name='RMS absolute acceleration '+comp+' - base '+axis
  rv_enum(q,'NormalOrientation',comp+'Axis');q.AccelerationInG=True;rvresults.append(q)
 eqa=a.Solution.AddEquivalentStressPSD();eqa.Name='RMS equivalent stress - all bodies';rvresults.append(eqa)
 eqp=a.Solution.AddEquivalentStressPSD();eqp.Name='RMS equivalent stress - PCB'
 sel=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities);sel.Ids=[42342];eqp.Location=sel;rvresults.append(eqp)
 for eq in [eqa,eqp]:rv_enum(eq,'DisplayOption','Unaveraged')
 for comp in ['X','Y','Z']:
  st=a.Solution.AddNormalElasticStrain();st.Name='RMS PCB normal strain '+comp
  rv_enum(st,'NormalOrientation',comp+'Axis');st.Location=sel;rv_enum(st,'DisplayOption','Unaveraged');rvresults.append(st)
System.IO.File.WriteAllText(RV_ROOT+r'\results_configured.txt','\n'.join(unicode(o.ObjectId)+'|'+unicode(o.Name)+'|'+unicode(o.ObjectState) for o in rvresults))
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')

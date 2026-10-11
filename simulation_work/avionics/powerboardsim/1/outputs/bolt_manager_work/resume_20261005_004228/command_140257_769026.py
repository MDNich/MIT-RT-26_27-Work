ms=rvmodal.AnalysisSettings
ms.SaveMAPDLDB=True
ms.SkipExpansion=False
rv_enum(ms,'StoreModalResults','Yes')
s=[]
for a,axis in zip(rvs,['X','Y','Z']):
 aset=a.AnalysisSettings
 rv_enum(aset,'ConstantDamping','Manual')
 aset.DampingRatio=0.02
 aset.CalculateAcceleration=True
 aset.CalculateVelocity=True
 aset.KeepModalResults=True
 aset.ExcludeInsignificantModes=False
 aset.ModeSignificanceLevel=0.0
 aset.SaveMAPDLDB=True
 load=[x for x in a.Children if unicode(x.DataModelObjectCategory)=='PSDGAcceleration'][0]
 rv_enum(load,'Direction',axis+'Axis')
 load.BoundaryCondition=ExtAPI.DataModel.GetObjectById(4127)
 load.LoadData.Inputs[0].DiscreteValues=[Quantity(unicode(v)+' [Hz]') for v in [20,50,800,2000]]
 load.LoadData.Output.DiscreteValues=[Quantity(unicode(v)+' [gravity gravity Hz^-1]') for v in [.026,.16,.16,.026]]
 s.append('%s|%s|%s|%s|%s|%s'%(a.ObjectId,axis,aset.DampingRatio,load.BoundaryCondition,load.Direction,load.ObjectState))
System.IO.File.WriteAllText(RV_ROOT+r'\psd_setup_verified.txt','\n'.join(s))
System.IO.Directory.CreateDirectory(RV_ROOT+r'\modal_basis')
bm.StartApdlInputFileWrite(rvmodal)
rvmodal.WriteInputFile(RV_ROOT+r'\modal_basis\modal_input.dat')
System.IO.File.WriteAllText(RV_ROOT+r'\modal_basis\EXPORTED.txt',unicode(rvmodal.ObjectState)+'\n'+unicode(rvmodal.WorkingDir))
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')

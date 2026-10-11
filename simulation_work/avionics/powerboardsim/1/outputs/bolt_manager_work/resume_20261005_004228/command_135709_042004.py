def rv_enum(o,name,value):
 p=o.GetType().GetProperty(name)
 p.SetValue(o,System.Enum.Parse(p.PropertyType,value),None)
rv_enum(ms,'NodalForces','Yes')
ms.CalculateReactions=True
ms.ContactSplit=orig.ContactSplit
ms.SolverType=orig.SolverType
ms.RetainFilesAfterFullSolve=orig.RetainFilesAfterFullSolve
ms.SolverUnits=orig.SolverUnits
ms.SolverUnitSystem=orig.SolverUnitSystem
ms.SkipExpansion=False
ms.SaveMAPDLDB=True
rv_enum(ms,'StoreModalResults','Yes')
System.IO.File.WriteAllText(RV_ROOT+r'\modal_settings_written.txt',unicode(ms.MaximumModesToFind)+'\n'+unicode(rvic.PreStressICEnvironment.ObjectId))
rvs=[]
for axis in ['X','Y','Z']:
 a=ExtAPI.DataModel.Project.Model.AddRandomVibrationAnalysis()
 rvs.append(a)
 System.IO.File.WriteAllText(RV_ROOT+r'\new_random_ids.txt','\n'.join(unicode(x.ObjectId) for x in rvs))
System.IO.File.WriteAllText(RV_ROOT+r'\random_created.txt',System.DateTime.UtcNow.ToString('o'))

rvmodal=ExtAPI.DataModel.GetObjectById(4254)
rvmodal.Name='RANDOM VIBE - expanded prestressed modal basis'
rvic=[x for x in list(rvmodal.Children) if unicode(x.DataModelObjectCategory)=='InitialCondition'][0]
rvic.PreStressICEnvironment=ExtAPI.DataModel.GetObjectById(4123)
ms=rvmodal.AnalysisSettings
orig=ExtAPI.DataModel.GetObjectById(1656).AnalysisSettings
ms.MaximumModesToFind=60
ms.LimitSearchToRange=True
ms.SearchRangeMinimum=Quantity('1 [Hz]')
ms.SearchRangeMaximum=Quantity('4000 [Hz]')
ms.Damped=False
ms.Stress=True
ms.Strain=True
ms.NodalForces=True
ms.ContactSplit=orig.ContactSplit
ms.SolverType=orig.SolverType
ms.RetainFilesAfterFullSolve=orig.RetainFilesAfterFullSolve
ms.SolverUnits=orig.SolverUnits
ms.SolverUnitSystem=orig.SolverUnitSystem
ms.SkipExpansion=False
System.IO.File.WriteAllText(RV_ROOT+r'\modal_settings_written.txt',unicode(ms.MaximumModesToFind)+'\n'+unicode(rvic.PreStressICEnvironment.ObjectId))
rvs=[]
for axis in ['X','Y','Z']:
 a=ExtAPI.DataModel.Project.Model.AddRandomVibrationAnalysis()
 rvs.append(a)
 System.IO.File.WriteAllText(RV_ROOT+r'\new_random_ids.txt','\n'.join(unicode(x.ObjectId) for x in rvs))
System.IO.File.WriteAllText(RV_ROOT+r'\random_created.txt',System.DateTime.UtcNow.ToString('o'))

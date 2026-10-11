try:
 ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
 pba=ExtAPI.DataModel.GetObjectById(4559);pbr=ExtAPI.DataModel.GetObjectById(4566)
 pba.InitialConditions[0].ModalEnvironmentTransientMSUPIC=ExtAPI.DataModel.GetObjectById(4254)
 pba.AnalysisSettings.StepEndTime=Quantity(.25,'s')
 pba.Solution.ReadGivenAnsysResultFileByReference(pbmotionroot+r'\pilot_expand_nodal\file.rst',UnitSystemIDType.UnitsMKS)
 pbr.SetNumber=1;pba.Solution.EvaluateAllResults();pbr.Activate()
 System.IO.File.WriteAllText(pbmotionroot+r'\pilot_expand_nodal\linked_check2.txt',str(pbr.ObjectState)+' '+str(pbr.Maximum)+' '+str(pbr.Time))
except Exception as ex:
 System.IO.File.WriteAllText(pbmotionroot+r'\pilot_expand_nodal\linked_error2.txt',str(ex))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

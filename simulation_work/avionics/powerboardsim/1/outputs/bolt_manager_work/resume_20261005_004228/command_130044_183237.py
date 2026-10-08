ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
pba=ExtAPI.DataModel.GetObjectById(4559);pbas=pba.AnalysisSettings
pbas.StepEndTime=Quantity(.25,'s')
pbas.AutomaticTimeStepping=AutomaticTimeStepping.Off
pbas.TimeStep=Quantity(1.0/32768,'s')
pbas.InitialTimeStep=Quantity(1.0/32768,'s');pbas.MinimumTimeStep=Quantity(1.0/32768,'s');pbas.MaximumTimeStep=Quantity(1.0/32768,'s')
pba.Solution.ReadGivenAnsysResultFileByReference(pbmotionroot+r'\pilot_expand_nodal\file.rst',UnitSystemIDType.UnitsMKS)
pbr=ExtAPI.DataModel.GetObjectById(4567)
pbp=pbr.GetType().GetProperty('By');pbp.SetValue(pbr,System.Enum.Parse(pbp.PropertyType,'ResultSet'),None);pbr.SetNumber=1
pbr.EvaluateAllResults();pbr.Activate()
System.IO.File.WriteAllText(pbmotionroot+r'\pilot_expand_nodal\timestep_fixed.txt',unicode(pbr.ObjectState)+' '+unicode(pbr.Maximum))

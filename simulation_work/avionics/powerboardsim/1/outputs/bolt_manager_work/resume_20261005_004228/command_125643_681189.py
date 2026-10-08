ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
pba=ExtAPI.DataModel.GetObjectById(4559)
pbr2=pba.Solution.AddTotalDeformation();pbr2.Name='Time-history displacement - display check'
pbr2.CalculateTimeHistory=False
pba.Solution.EvaluateAllResults()
System.IO.File.WriteAllText(pbmotionroot+r'\pilot_expand_nodal\new_result_id.txt',str(pbr2.ObjectId))

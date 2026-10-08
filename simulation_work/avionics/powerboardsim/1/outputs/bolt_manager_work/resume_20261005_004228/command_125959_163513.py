pbas=ExtAPI.DataModel.GetObjectById(4559).AnalysisSettings
System.IO.File.WriteAllLines(pbmotionroot+r'\pilot_expand_nodal\timestep_api.txt',[unicode(x) for x in pbas.GetType().GetMethods() if any(s in x.Name for s in ['TimeStep','Substep','StepEnd','DefineBy','Integration'])])

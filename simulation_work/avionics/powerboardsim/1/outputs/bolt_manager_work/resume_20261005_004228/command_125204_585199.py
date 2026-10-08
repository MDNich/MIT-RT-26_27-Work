try:
 ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
 pba=ExtAPI.DataModel.GetObjectById(4559);pbr=ExtAPI.DataModel.GetObjectById(4566)
 pbr.CalculateTimeHistory=False
 pbnames=[str(x.DisplayString) for x in ExtAPI.Application.Messages]
 pbr.EvaluateAllResults()
 pbl=['IC='+str(pba.InitialConditions[0].ModalEnvironmentTransientMSUPIC),'A='+str(pba.ObjectState),'S='+str(pba.Solution.ObjectState),'R='+str(pbr.ObjectState),'WorkingDir='+str(pba.WorkingDir)]
 for pbm in ExtAPI.Application.Messages:
  if str(pbm.DisplayString) not in pbnames:pbl.append(str(pbm.DisplayString))
 for pbo in [pba,pba.Solution,pbr]:
  for pbp in pbo.Properties:
   if any(s in str(pbp.Name).lower() for s in ['file','error','valid','state','result','read','time','modal','solution']):
    try:pbl.append(str(pbo.ObjectId)+' '+str(pbp.Name)+'='+str(pbp.InternalValue))
    except:pass
 System.IO.File.WriteAllLines(pbmotionroot+r'\pilot_expand_nodal\evaluation_diagnostic.txt',pbl)
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

with open(pbmotionroot+r'\control\license_reactivate.txt','w') as f:
 lp=ExtAPI.Application.LicensePreference
 f.write('Before '+str(ExtAPI.Application.ActiveUnitSystem)+'\n')
 try:
  lp.ActivateLicense('Ansys Mechanical Enterprise')
  f.write('ACTIVATED\n')
  r=ExtAPI.DataModel.GetObjectById(4207);r.EvaluateAllResults()
  f.write(str(r.ObjectState)+' '+str(r.Maximum)+'\n')
 except Exception as e:f.write(str(e)+'\n')

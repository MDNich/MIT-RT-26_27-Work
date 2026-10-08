try:
 ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
 pba=ExtAPI.DataModel.GetObjectById(4559);pbr=ExtAPI.DataModel.GetObjectById(4566)
 pbnames=[unicode(x.DisplayString) for x in ExtAPI.Application.Messages]
 pba.Solution.ReadGivenAnsysResultFile(pbmotionroot+r'\pilot_expand_nodal\file.rst',UnitSystemIDType.UnitsMKS)
 pbr.SetNumber=1;pbr.EvaluateAllResults();pbr.Activate()
 pbl=['A='+unicode(pba.ObjectState),'S='+unicode(pba.Solution.ObjectState),'R='+unicode(pbr.ObjectState),'Max='+unicode(pbr.Maximum)]
 for pbm in ExtAPI.Application.Messages:
  if unicode(pbm.DisplayString) not in pbnames:pbl.append(unicode(pbm.DisplayString))
 System.IO.File.WriteAllLines(pbmotionroot+r'\pilot_expand_nodal\full_license_check.txt',pbl)
except Exception as ex:
 System.IO.File.WriteAllText(pbmotionroot+r'\pilot_expand_nodal\full_license_error.txt',unicode(ex))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

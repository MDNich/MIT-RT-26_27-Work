import System
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import UnitSystemIDType
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
pba=ExtAPI.DataModel.Project.Model.AddTransientStructuralAnalysis()
pba.Name='Representative random motion - validation only'
System.IO.File.WriteAllText(pbmotionroot+r'\pilot_expand_nodal\analysis_id.txt',str(pba.ObjectId))
pba.Solution.ReadGivenAnsysResultFileByReference(pbmotionroot+r'\pilot_expand_nodal\file.rst',UnitSystemIDType.UnitsMKS)
pbr=pba.Solution.AddDirectionalDeformation();pbr.Name='Instantaneous displacement X - validation'
pbr.NormalOrientation=NormalOrientationType.XAxis
pbr.DisplayTime=Quantity(.20006103515625,'s');pbr.EvaluateAllResults();pbr.Activate()
pbread=pba.GetResultsData()
pbl=['Result='+str(pbr.ObjectId),'Times='+str(list(pbread.ListTimeFreq)),'Maximum='+str(pbr.Maximum)]
for pbi in range(1,5):
 pbread.CurrentResultSet=pbi;pbu=pbread.GetResult('U')
 for pbn in [44,2064,2075,2185,42154,42242,136765]:pbl.append(str(pbi)+','+str(pbn)+','+','.join(str(x) for x in pbu.GetNodeValues(pbn)))
pbread.Dispose()
System.IO.File.WriteAllLines(pbmotionroot+r'\pilot_expand_nodal\mechanical_check.txt',pbl)

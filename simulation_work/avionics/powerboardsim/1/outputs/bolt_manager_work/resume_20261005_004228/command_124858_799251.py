import System
from Ansys.Core.Units import Quantity
try:
 ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
 pbr=ExtAPI.DataModel.GetObjectById(4566)
 pbp=pbr.GetType().GetProperty('By');pbp.SetValue(pbr,System.Enum.Parse(pbp.PropertyType,'ResultSet'),None)
 pbr.SetNumber=1;pbr.EvaluateAllResults();pbr.Activate()
 System.IO.File.WriteAllText(pbmotionroot+r'\pilot_expand_nodal\resultset_check.txt',str(pbr.ObjectState)+' '+str(pbr.Maximum)+' '+str(pbr.Time))
 pbs=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();pbs.Width=3840;pbs.Height=2160;pbs.CurrentGraphicsDisplay=False
 ExtAPI.Graphics.ExportImage(pbmotionroot+r'\pilot_expand_nodal\first_frame.png',GraphicsImageExportFormat.PNG,pbs)
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

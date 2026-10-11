import System,mech_dpf
import Ans.DataProcessing as dpf
from Ansys.Core.Units import Quantity
mech_dpf.setExtAPI(ExtAPI)
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+r'\control\MODAL_RESULT_ID.txt')))
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference
 out=r'C:\Temp\PBMotionWarpScale';System.IO.Directory.CreateDirectory(out)
 System.IO.File.WriteAllText(r'C:\Temp\PBMotionControl\modal_frame.txt','45');r.ClearGeneratedData();r.EvaluateAllResults();r.Activate()
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 rows=[]
 import pcb_modal_motion_v2 as sm
 co,wa=sm.fields(45)
 for f in [co[0],wa[0]]:rows.append('Field: '+str(f.Unit)+' '+str(f.Location)+' '+str(f.GetType()))
 for factor in [0.003/7.160033972903191,3./7.160033972903191]:
  pref.DeformationScaleMultiplier=factor
  rows.append('Scale: '+str(pref.DeformationScaleMultiplier))
  G.ExportImage(out+'\\scale_'+str(int(factor*1000000))+'.png',GraphicsImageExportFormat.PNG,settings)
 System.IO.File.WriteAllLines(pbmotionroot+r'\control\warp_scale_probe.txt',rows)
finally:ExtAPI.Application.LicensePreference.DeActivateLicense()

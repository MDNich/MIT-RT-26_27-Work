import System
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 out=r'C:\Temp\PBMotionWarpCompare';System.IO.Directory.CreateDirectory(out)
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 for mode,native_id,frame,factor in [('stress',4589,1,50),('modal',4207,45,0.003/7.160033972903191)]:
  custom=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+'\\control\\'+mode.upper()+'_RESULT_ID.txt')))
  System.IO.File.WriteAllText('C:\\Temp\\PBMotionControl\\'+mode+'_frame.txt',str(frame))
  custom.ClearGeneratedData();custom.EvaluateAllResults();custom.Activate();pref.DeformationScaleMultiplier=factor
  G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
  height=G.Camera.SceneHeight;focal=G.Camera.FocalPoint
  G.ExportImage(out+'\\'+mode+'_custom.png',GraphicsImageExportFormat.PNG,settings)
  r=ExtAPI.DataModel.GetObjectById(native_id)
  if mode=='stress':r.SetNumber=1;r.EvaluateAllResults()
  r.Activate();pref.DeformationScaleMultiplier=factor
  G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.FocalPoint=focal;G.Camera.SceneHeight=height
  G.ExportImage(out+'\\'+mode+'_native.png',GraphicsImageExportFormat.PNG,settings)
 System.IO.File.WriteAllText(pbmotionroot+r'\control\WARP_COMPARE_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
finally:ExtAPI.Application.LicensePreference.DeActivateLicense()

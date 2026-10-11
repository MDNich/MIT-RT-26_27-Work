import System
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 out=r'C:\Temp\PBMotionBitmapPilot';System.IO.Directory.CreateDirectory(out);rows=[]
 for mode,nums,factor in [('modal',[0,45,135],3./7.160033972903191),('stress',[1,120],50000)]:
  r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+'\\control\\'+mode.upper()+'_RESULT_ID.txt')))
  for n in nums:
   clock=System.Diagnostics.Stopwatch.StartNew()
   System.IO.File.WriteAllText('C:\\Temp\\PBMotionControl\\'+mode+'_frame.txt',str(n))
   r.ClearGeneratedData();r.EvaluateAllResults();r.Activate();pref.DeformationScaleMultiplier=factor
   if n==nums[0]:G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
   evaltime=clock.Elapsed.TotalSeconds
   G.ExportImage(out+'\\'+mode+'_%03d.bmp'%n,GraphicsImageExportFormat.BMP,settings)
   rows.append(repr({'mode':mode,'frame':n,'evaluation_s':evaltime,'total_s':clock.Elapsed.TotalSeconds}))
   System.IO.File.WriteAllLines(pbmotionroot+r'\control\bmp_pilot_audit.txt',rows)
 System.IO.File.WriteAllText(pbmotionroot+r'\control\BMP_PILOT_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
finally:ExtAPI.Application.LicensePreference.DeActivateLicense()

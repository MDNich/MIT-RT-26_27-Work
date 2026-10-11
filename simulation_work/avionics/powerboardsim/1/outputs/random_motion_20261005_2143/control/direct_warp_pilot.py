import System,sys,mech_dpf
from Ansys.Core.Units import Quantity
mech_dpf.setExtAPI(ExtAPI)
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 out=r'C:\Temp\PBMotionDirectPilot';System.IO.Directory.CreateDirectory(out);rows=[]
 for mode,nums,factor in [('modal',[0,45,135],3./7.160033972903191),('stress',[1,120],50000)]:
  sm=__import__('pcb_'+mode+'_motion_v5')
  r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+'\\control\\'+mode.upper()+'_RESULT_ID.txt')))
  for n in nums:
   clock=System.Diagnostics.Stopwatch.StartNew()
   System.IO.File.WriteAllText('C:\\Temp\\PBMotionControl\\'+mode+'_frame.txt',str(n))
   sm.workflow(r);wfsecs=clock.Elapsed.TotalSeconds
   r.Evaluate();r.Activate();pref.DeformationScaleMultiplier=factor;evalsecs=clock.Elapsed.TotalSeconds
   if n==nums[0]:G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
   G.ExportImage(out+'\\'+mode+'_%03d.png'%n,GraphicsImageExportFormat.PNG,settings)
   rows.append(repr({'mode':mode,'frame':n,'workflow_s':wfsecs,'evaluation_s':evalsecs-wfsecs,'total_s':clock.Elapsed.TotalSeconds,'audit':sm.last}))
   System.IO.File.WriteAllLines(pbmotionroot+r'\control\direct_pilot_audit.txt',rows)
 System.IO.File.WriteAllText(pbmotionroot+r'\control\DIRECT_PILOT_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
finally:ExtAPI.Application.LicensePreference.DeActivateLicense()

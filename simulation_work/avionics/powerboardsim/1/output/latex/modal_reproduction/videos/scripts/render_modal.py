import System,math
from Ansys.Core.Units import Quantity
assert System.IO.File.Exists(pbmotionroot+r'\control\MODAL_PILOT_V5_COMPLETE.txt')
assert System.IO.File.Exists(pbmotionroot+r'\MOTION_PILOT_ACCEPTED.json')
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+r'\control\MODAL_RESULT_ID.txt')))
 out=r'C:\Temp\PBMotionVideos\modal_fig03_bolted_mode20'
 System.IO.Directory.CreateDirectory(out+r'\frames')
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference
 p=pref.GetType().GetProperty('DeformationScaling');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'True'),None)
 pref.DeformationScaleMultiplier=3./7.160033972903191
 pref.ShowMaximum=False;pref.ShowMinimum=False
 G.ViewOptions.ShowMesh=False;G.ViewOptions.ShowLogo=False;G.ViewOptions.ShowRuler=False
 G.GlobalLegendSettings.ShowDateAndTime=False;G.GlobalLegendSettings.ShowMinMax=False
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 audits=[]
 clock=System.Diagnostics.Stopwatch.StartNew()
 for index in range(180):
  if System.IO.File.Exists(r'C:\Temp\PBMotionControl\STOP_RENDER.txt'):raise Exception('Render stop requested at frame boundary')
  System.IO.File.WriteAllText(r'C:\Temp\PBMotionControl\modal_frame.txt',str(index))
  r.ClearGeneratedData();r.EvaluateAllResults();r.Activate();pref.DeformationScaleMultiplier=3./7.160033972903191
  a=eval(System.IO.File.ReadAllText(r'C:\Temp\PBMotionControl\modal_last.txt'))
  assert a['frame']==index and abs(a['phase_factor']-math.sin(2*math.pi*index/180.))<1e-12
  assert abs(a['normalized_maximum']-7.160033972903191)<1e-5
  if index==0:
   G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
   System.IO.File.WriteAllLines(out+r'\camera_audit.txt',[str(G.Camera.SceneHeight),str(G.Camera.ViewVector),str(G.Camera.UpVector),str(G.Camera.FocalPoint)])
  legend=Ansys.Mechanical.Graphics.Tools.CurrentLegendSettings();legend.NumberOfBands=10
  for band in range(10):
   legend.SetLowerBound(band,Quantity(7.160033972903191*band/10.,'m'));legend.SetUpperBound(band,Quantity(7.160033972903191*(band+1)/10.,'m'))
  if index==0:G.ExportImage(out+r'\legend_verified.png',GraphicsImageExportFormat.PNG,settings)
  G.ExportImage(out+r'\frames\AnimationFrame%06d.png'%index,GraphicsImageExportFormat.PNG,settings)
  audits.append(repr(a));System.IO.File.WriteAllLines(out+r'\field_audit.txt',audits)
  System.IO.File.WriteAllText(out+r'\progress.txt',str(index+1)+','+str(clock.Elapsed.TotalSeconds))
  if index%30==0:System.GC.Collect()
 System.IO.File.WriteAllText(out+r'\COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
 System.IO.File.WriteAllText(pbmotionroot+r'\control\MODAL_RENDER_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

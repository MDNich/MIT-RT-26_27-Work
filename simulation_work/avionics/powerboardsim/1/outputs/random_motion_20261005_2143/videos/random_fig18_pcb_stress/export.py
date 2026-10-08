import System,math
from Ansys.Core.Units import Quantity
assert System.IO.File.Exists(pbmotionroot+r'\control\STRESS_PILOT_V5_COMPLETE.txt')
assert System.IO.File.Exists(pbmotionroot+r'\MOTION_PILOT_ACCEPTED.json')
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+r'\control\STRESS_RESULT_ID.txt')))
 reference=eval(System.IO.File.ReadAllText(pbmotionroot+r'\control\stress_reference.pydata'))
 assert len(reference)==480
 out=r'C:\Temp\PBMotionVideos\random_fig18_pcb_stress';host=pbmotionroot+r'\videos\random_fig18_pcb_stress'
 System.IO.Directory.CreateDirectory(out+r'\frames')
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference
 p=pref.GetType().GetProperty('DeformationScaling');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'True'),None);pref.DeformationScaleMultiplier=50000
 pref.ShowMaximum=False;pref.ShowMinimum=False
 G.ViewOptions.ShowMesh=False;G.ViewOptions.ShowLogo=False;G.ViewOptions.ShowRuler=False;G.GlobalLegendSettings.ShowDateAndTime=False;G.GlobalLegendSettings.ShowMinMax=False
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 bound=160000000.0;System.IO.File.WriteAllText(out+r'\legend_bound_Pa.txt',str(bound))
 rows=['frame,set,time_s,maximum_Pa,minimum_Pa'];audits=[]
 clock=System.Diagnostics.Stopwatch.StartNew()
 for number in range(1,481):
  if System.IO.File.Exists(r'C:\Temp\PBMotionControl\STOP_RENDER.txt'):raise Exception('Render stop requested at frame boundary')
  System.IO.File.WriteAllText(r'C:\Temp\PBMotionControl\stress_frame.txt',str(number))
  r.ClearGeneratedData();r.EvaluateAllResults();r.Activate();pref.DeformationScaleMultiplier=50000
  audit=eval(System.IO.File.ReadAllText(r'C:\Temp\PBMotionControl\stress_last.txt'))
  assert audit['frame']==number and abs(audit['time_s']-(1+number/16384.))<1e-12
  assert abs(audit['maximum_Pa']-reference[number-1]['maximum_Pa'])<1e-7*max(1,audit['maximum_Pa'])
  assert audit['maximum_Pa']<=bound and audit['minimum_Pa']>=0
  assert max(abs(x) for x in audit['u_nodes'][136765])<1e-12
  if number==1:
   G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
   System.IO.File.WriteAllLines(out+r'\camera_audit.txt',[str(G.Camera.SceneHeight),str(G.Camera.ViewVector),str(G.Camera.UpVector),str(G.Camera.FocalPoint)])
  legend=Ansys.Mechanical.Graphics.Tools.CurrentLegendSettings();legend.NumberOfBands=10
  for band in range(10):
   legend.SetLowerBound(band,Quantity(bound*band/10.,'Pa'));legend.SetUpperBound(band,Quantity(bound*(band+1)/10.,'Pa'))
  if number==1:G.ExportImage(out+r'\legend_verified.png',GraphicsImageExportFormat.PNG,settings)
  G.ExportImage(out+r'\frames\AnimationFrame%06d.png'%(number-1),GraphicsImageExportFormat.PNG,settings)
  rows.append('%d,%d,%.17g,%.17g,%.17g'%(number-1,number,audit['time_s'],audit['maximum_Pa'],audit['minimum_Pa']))
  audits.append(repr(audit));System.IO.File.WriteAllLines(out+r'\frame_audit.csv',rows);System.IO.File.WriteAllLines(out+r'\field_audit.txt',audits)
  System.IO.File.WriteAllText(out+r'\progress.txt',str(number)+','+str(clock.Elapsed.TotalSeconds))
  if number%40==0:System.GC.Collect()
 System.IO.File.WriteAllText(out+r'\COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
 System.IO.File.WriteAllText(host+r'\RENDERED.txt',System.DateTime.UtcNow.ToString('o'))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

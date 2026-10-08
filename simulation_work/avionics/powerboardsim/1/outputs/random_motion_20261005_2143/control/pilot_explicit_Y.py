JOB={'result': 4569, 'camera': 'Battery', 'sets': [1, 2, 120, 480], 'local_output': 'C:\\Temp\\PBMotionVideos\\pilot_explicit_Y', 'host_output': 'Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_motion_20261005_2143\\pilot_explicit_Y'}
# JOB is inserted by controller. Native result sets, no camera motion or reverse playback.
import System,math
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
try:
 r=ExtAPI.DataModel.GetObjectById(JOB['result']);r.Activate();G=ExtAPI.Graphics
 out=JOB['local_output'];System.IO.Directory.CreateDirectory(out)
 bound=max(abs(r.MaximumOfMaximumOverTime.Value),abs(r.MinimumOfMinimumOverTime.Value))
 assert bound>0
 step=10**(math.floor(math.log10(bound))-1);bound=math.ceil(bound/step)*step
 G.ViewOptions.ShowMesh=False;G.ViewOptions.ShowLogo=False;G.ViewOptions.ShowRuler=False;G.GlobalLegendSettings.ShowDateAndTime=False;G.GlobalLegendSettings.ShowMinMax=False
 pref=G.ViewOptions.ResultPreference;pref.ShowMaximum=False;pref.ShowMinimum=False
 p=pref.GetType().GetProperty('DeformationScaling');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'True'),None);pref.DeformationScaleMultiplier=50
 for b in ExtAPI.DataModel.Project.Model.Geometry.GetChildren(DataModelObjectCategory.Body,True):
  if hasattr(b,'Hidden') and b.Hidden:b.Hidden=False
 legend=Ansys.Mechanical.Graphics.Tools.CurrentLegendSettings();legend.NumberOfBands=10
 for i in range(10):
  legend.SetLowerBound(i,Quantity(-bound+2*bound*i/10.,'m'));legend.SetUpperBound(i,Quantity(-bound+2*bound*(i+1)/10.,'m'))
 if JOB['camera']=='Battery':
  G.Camera.ViewVector=Ansys.ACT.Math.Vector3D(1,-1,-1);G.Camera.UpVector=Ansys.ACT.Math.Vector3D(-.3,1,-1.3)
 else:G.Camera.SetSpecificViewOrientation(getattr(ViewOrientationType,JOB['camera']))
 G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
 s=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();s.Width=3840;s.Height=2160;s.CurrentGraphicsDisplay=False;s.FontMagnification=.85
 G.ExportImage(out+r'\legend_verified.png',GraphicsImageExportFormat.PNG,s)

 System.IO.File.WriteAllText(out+r'\STARTED.txt',System.DateTime.UtcNow.ToString('o'))
 System.IO.File.WriteAllText(out+r'\legend_bound_m.txt',str(bound))
 frames=out+r'\frames';System.IO.Directory.CreateDirectory(frames)
 r.CalculateTimeHistory=False
 p=r.GetType().GetProperty('By');p.SetValue(r,System.Enum.Parse(p.PropertyType,'ResultSet'),None)
 audit=['frame,set,time_s,maximum_m,minimum_m']
 for index,number in enumerate(JOB.get('sets',range(1,481))):
  r.SetNumber=number;r.EvaluateAllResults();r.Activate()
  # Reassert constant contour scale after each result refresh.
  legend=Ansys.Mechanical.Graphics.Tools.CurrentLegendSettings();legend.NumberOfBands=10
  for b in range(10):
   legend.SetLowerBound(b,Quantity(-bound+2*bound*b/10.,'m'));legend.SetUpperBound(b,Quantity(-bound+2*bound*(b+1)/10.,'m'))
  G.ExportImage(frames+r'\AnimationFrame%06d.png'%index,GraphicsImageExportFormat.PNG,s)
  audit.append('%d,%d,%.17g,%.17g,%.17g'%(index,number,r.Time.Value,r.Maximum.Value,r.Minimum.Value))
  System.IO.File.WriteAllLines(out+r'\frame_audit.csv',audit)
 System.IO.File.WriteAllText(out+r'\COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
 System.IO.File.WriteAllText(JOB['host_output']+r'\RENDERED.txt',System.DateTime.UtcNow.ToString('o'))

finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

JOB={'result': 4605, 'camera': 'Iso', 'local_output': 'C:\\Temp\\PBMotionVideos\\random_fig17_pcb_baseZ', 'host_output': 'Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_motion_20261005_2143\\videos\\random_fig17_pcb_baseZ'}
# JOB is inserted by controller. Native result sets, no camera motion or reverse playback.
import System,math
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
try:
 r=ExtAPI.DataModel.GetObjectById(JOB['result']);r.CalculateTimeHistory=True;r.Activate();G=ExtAPI.Graphics
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
 o=G.ResultAnimationOptions;o.NumberOfFrames=480;o.Duration=Quantity(8,'s');o.UpdateContourRangeAtEachFrame=False;o.FitDeformationScalingToAnimation=False
 p=o.GetType().GetProperty('RangeType');p.SetValue(o,System.Enum.Parse(p.PropertyType,'ResultSets'),None)
 f=o.GetType().GetField('_animationControl',System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic);c=f.GetValue(o)
 f.FieldType.GetProperty('ForwardBackwardMode').SetValue(c,System.Int32(0),None)
 f.FieldType.GetMethod('SetExportStreamWidthHeight').Invoke(c,System.Array[System.Object]([System.Int32(3840),System.Int32(2160)]))
 ss=Ansys.Mechanical.Graphics.AnimationExportSettings(3840,2160);ss.TemporaryFramesPath=out+r'\frames';System.IO.Directory.CreateDirectory(ss.TemporaryFramesPath)
 System.IO.File.WriteAllText(out+r'\STARTED.txt',System.DateTime.UtcNow.ToString('o'))
 System.IO.File.WriteAllText(out+r'\legend_bound_m.txt',str(bound))
 r.ExportAnimation(out+r'\native.mp4',GraphicsAnimationExportFormat.MP4,ss)
 System.IO.File.WriteAllText(out+r'\COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
 System.IO.File.WriteAllText(JOB['host_output']+r'\RENDERED.txt',System.DateTime.UtcNow.ToString('o'))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

import System,math
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
try:
 r=ExtAPI.DataModel.GetObjectById(4571);r.Activate();G=ExtAPI.Graphics
 r.CalculateTimeHistory=True
 out=pbmotionroot+r'\videos\random_fig06_baseX_responseX';System.IO.Directory.CreateDirectory(out)
 bound=max(abs(r.MaximumOfMaximumOverTime.Value),abs(r.MinimumOfMinimumOverTime.Value));bound=math.ceil(bound*1e6/10)*10/1e6
 G.ViewOptions.ShowMesh=False;G.ViewOptions.ShowLogo=False;G.ViewOptions.ShowRuler=False;G.GlobalLegendSettings.ShowDateAndTime=False
 pref=G.ViewOptions.ResultPreference;pref.ShowMaximum=False;pref.ShowMinimum=False
 p=pref.GetType().GetProperty('DeformationScaling');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'True'),None);pref.DeformationScaleMultiplier=50
 legend=Ansys.Mechanical.Graphics.Tools.CurrentLegendSettings();legend.NumberOfBands=10
 for i in range(10):
  legend.SetLowerBound(i,Quantity(-bound+2*bound*i/10.,'m'));legend.SetUpperBound(i,Quantity(-bound+2*bound*(i+1)/10.,'m'))
 G.Camera.ViewVector=Ansys.ACT.Math.Vector3D(1,-1,-1);G.Camera.UpVector=Ansys.ACT.Math.Vector3D(-.3,1,-1.3);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
 s=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();s.Width=3840;s.Height=2160;s.CurrentGraphicsDisplay=False;s.FontMagnification=.85
 G.ExportImage(out+r'\legend_source.png',GraphicsImageExportFormat.PNG,s)
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
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

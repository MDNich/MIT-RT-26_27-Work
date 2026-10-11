ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
import System
from Ansys.Core.Units import Quantity
try:
 pbr=ExtAPI.DataModel.GetObjectById(4567);pbr.CalculateTimeHistory=True;pbr.EvaluateAllResults();pbr.Activate();pbg=ExtAPI.Graphics
 pbg.ViewOptions.ShowMesh=False;pbg.ViewOptions.ShowLogo=False;pbg.GlobalLegendSettings.ShowDateAndTime=False
 pbpref=pbg.ViewOptions.ResultPreference
 pbp=pbpref.GetType().GetProperty('DeformationScaling');pbp.SetValue(pbpref,System.Enum.Parse(pbp.PropertyType,'True'),None);pbpref.DeformationScaleMultiplier=50
 pbg.Camera.ViewVector=Ansys.ACT.Math.Vector3D(1,-1,-1);pbg.Camera.UpVector=Ansys.ACT.Math.Vector3D(-.3,1,-1.3);pbg.Camera.SetFit();pbg.Camera.SceneHeight=Quantity(pbg.Camera.SceneHeight.Value*1.3,'mm')
 pbo=pbg.ResultAnimationOptions;pbo.NumberOfFrames=4;pbo.Duration=Quantity(4.0/60,'s');pbo.UpdateContourRangeAtEachFrame=False;pbo.FitDeformationScalingToAnimation=False
 pbp=pbo.GetType().GetProperty('RangeType');pbp.SetValue(pbo,System.Enum.Parse(pbp.PropertyType,'ResultSets'),None)
 pbf=pbo.GetType().GetField('_animationControl',System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic);pbc=pbf.GetValue(pbo)
 pbf.FieldType.GetProperty('ForwardBackwardMode').SetValue(pbc,System.Int32(0),None)
 pbf.FieldType.GetMethod('SetExportStreamWidthHeight').Invoke(pbc,System.Array[System.Object]([System.Int32(3840),System.Int32(2160)]))
 pbout=pbmotionroot+r'\pilot_expand_nodal\native_history_4k';System.IO.Directory.CreateDirectory(pbout)
 pbs=Ansys.Mechanical.Graphics.AnimationExportSettings(3840,2160);pbs.TemporaryFramesPath=pbout+r'\frames';System.IO.Directory.CreateDirectory(pbs.TemporaryFramesPath)
 pbr.ExportAnimation(pbout+r'\native.mp4',GraphicsAnimationExportFormat.MP4,pbs)
 System.IO.File.WriteAllText(pbout+r'\COMPLETE.txt',str(pbo.AcceleratedAnimationWillBeUsed))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

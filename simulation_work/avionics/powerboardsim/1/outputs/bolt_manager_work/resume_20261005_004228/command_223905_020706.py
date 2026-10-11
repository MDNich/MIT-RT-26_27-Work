import System
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsAnimationExportFormat,ViewOrientationType
pbout=pbmotionroot+r'\render_proof'
System.IO.Directory.CreateDirectory(pbout)
try:
 ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
 pbr=ExtAPI.DataModel.GetObjectById(4207)
 pbr.EvaluateAllResults();pbr.Activate()
 pbg=ExtAPI.Graphics
 pbg.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);pbg.Camera.SetFit()
 pbg.Camera.SceneHeight=Quantity(str(pbg.Camera.SceneHeight.Value*1.3)+' [mm]')
 pbo=pbg.ResultAnimationOptions
 pbo.NumberOfFrames=3;pbo.Duration=Quantity(.1,'s')
 pbf=pbo.GetType().GetField('_animationControl',System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)
 pbc=pbf.GetValue(pbo)
 pbf.FieldType.GetMethod('SetExportStreamWidthHeight').Invoke(pbc,System.Array[System.Object]([System.Int32(3840),System.Int32(2160)]))
 pbs=Ansys.Mechanical.Graphics.AnimationExportSettings(3840,2160)
 pbs.TemporaryFramesPath=pbout+r'\frames';System.IO.Directory.CreateDirectory(pbs.TemporaryFramesPath)
 System.IO.File.WriteAllText(pbout+r'\before.txt',str(pbr.ObjectState)+' '+str(pbr.Maximum)+' GPU='+str(pbo.AcceleratedAnimationWillBeUsed))
 pbr.ExportAnimation(pbout+r'\native.mp4',GraphicsAnimationExportFormat.MP4,pbs)
 System.IO.File.WriteAllText(pbout+r'\COMPLETE.txt','done')
except Exception as ex:
 System.IO.File.WriteAllText(pbout+r'\error.txt',str(ex))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

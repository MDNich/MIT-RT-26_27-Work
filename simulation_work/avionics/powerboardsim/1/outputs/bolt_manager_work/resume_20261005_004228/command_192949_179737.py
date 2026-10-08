
import System
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import GraphicsAnimationExportFormat,ViewOrientationType
VIDEO_ROOT='Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\video_4k60_20261005_1928'
r=ExtAPI.DataModel.GetObjectById(4207)
assert unicode(r.ObjectState)=='Solved'
before=r.Maximum.Value
r.Activate()
ExtAPI.Graphics.ViewOptions.ShowMesh=False
ExtAPI.Graphics.ViewOptions.ShowLogo=False
pref=ExtAPI.Graphics.ViewOptions.ResultPreference
pref.ShowMinimum=False;pref.ShowMaximum=True
for name,value in [('ExtraModelDisplay','NoWireframe'),('DeformationScaling','Auto')]:
 p=pref.GetType().GetProperty(name)
 choices=[n for n in System.Enum.GetNames(p.PropertyType) if value.lower() in n.lower()]
 p.SetValue(pref,System.Enum.Parse(p.PropertyType,choices[0]),None)
cam=ExtAPI.Graphics.Camera
cam.SetSpecificViewOrientation(ViewOrientationType.Iso);cam.SetFit()
cam.SceneHeight=Quantity(str(cam.SceneHeight.Value*1.20)+' [mm]')
options=ExtAPI.Graphics.ResultAnimationOptions
options.NumberOfFrames=60
options.Duration=Quantity(1,'s')
options.UpdateContourRangeAtEachFrame=False
options.FitDeformationScalingToAnimation=True
settings=Ansys.Mechanical.Graphics.AnimationExportSettings(3840,2160)
settings.TemporaryFramesPath=VIDEO_ROOT+r'\pilot_modal_frames'
System.IO.Directory.CreateDirectory(settings.TemporaryFramesPath)
System.IO.File.WriteAllText(VIDEO_ROOT+r'\pilot_modal_started.txt',System.DateTime.UtcNow.ToString('o')+'\nAcceleratedAnimationWillBeUsed='+str(options.AcceleratedAnimationWillBeUsed))
r.ExportAnimation(VIDEO_ROOT+r'\pilot_modal.mp4',GraphicsAnimationExportFormat.MP4,settings)
assert r.Maximum.Value==before
System.IO.File.WriteAllText(VIDEO_ROOT+r'\pilot_modal_complete.txt',System.DateTime.UtcNow.ToString('o'))

JOB={'name': 'modal_fig03_bolted_mode20', 'analysis': 1656, 'result': 4207, 'camera': 'Iso', 'maximum': 7.160033972903191, 'title': '750 N per bolt | Mode 20 | 2364.1791 Hz', 'kind': 'modal', 'frequency': 2364.1791196584404}
OUT='Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\video_4k60_20261005_1928\\modal_fig03_bolted_mode20'
import System,math
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsAnimationExportFormat,ViewOrientationType
flags=System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic
G=ExtAPI.Graphics
PREF=G.ViewOptions.ResultPreference
G.ViewOptions.ShowMesh=False;G.ViewOptions.ShowLogo=False
G.GlobalLegendSettings.ShowDateAndTime=False
PREF.ShowMinimum=False;PREF.ShowMaximum=True
p=PREF.GetType().GetProperty('ExtraModelDisplay');p.SetValue(PREF,System.Enum.Parse(p.PropertyType,'NoWireframe'),None)
p=PREF.GetType().GetProperty('DeformationScaling');p.SetValue(PREF,System.Enum.Parse(p.PropertyType,[v for v in System.Enum.GetNames(p.PropertyType) if 'auto' in v.lower()][0]),None)
G.ResultAnimationOptions.GetType().GetField('_animationControl',flags).GetValue(G.ResultAnimationOptions).Stop()
for b in ExtAPI.DataModel.Project.Model.Geometry.GetChildren(DataModelObjectCategory.Body,True):
 if hasattr(b,'Hidden') and b.Hidden:b.Hidden=False
r=ExtAPI.DataModel.GetObjectById(JOB['result'])
a=ExtAPI.DataModel.GetObjectById(JOB['analysis'])
before=r.Maximum.Value
assert abs(before-JOB['maximum'])<max(abs(JOB['maximum'])*1e-9,1e-12)
if JOB['analysis']!=4182:assert unicode(r.ObjectState)=='Solved'
r.Activate()
c=G.Camera
if JOB['camera']=='Battery':
 c.ViewVector=Ansys.ACT.Math.Vector3D(1,-1,-1);c.UpVector=Ansys.ACT.Math.Vector3D(-0.3,1,-1.3)
elif JOB['camera']=='ModalBattery':
 c.ViewVector=Ansys.ACT.Math.Vector3D(1,1,-1);c.UpVector=Ansys.ACT.Math.Vector3D(-1,2,1)
else:c.SetSpecificViewOrientation(getattr(ViewOrientationType,JOB['camera']))
c.SetFit();c.SceneHeight=Quantity(str(c.SceneHeight.Value*1.30)+' [mm]')
s=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();s.Width=3840;s.Height=2160;s.CurrentGraphicsDisplay=False;s.FontMagnification=0.85
System.IO.Directory.CreateDirectory(OUT)
System.IO.File.WriteAllText(OUT+r'\STARTED.txt',System.DateTime.UtcNow.ToString('o'))

reader=a.GetResultsData();fs=list(reader.ListTimeFreq);reader.Dispose()
assert len(fs)==20 and min([abs(x-JOB['frequency']) for x in fs])<1e-8
G.ExportImage(OUT+r'\legend_source.png',GraphicsImageExportFormat.PNG,s)
o=G.ResultAnimationOptions;o.NumberOfFrames=91;o.Duration=Quantity(1.5,'s');o.UpdateContourRangeAtEachFrame=False;o.FitDeformationScalingToAnimation=True
settings=Ansys.Mechanical.Graphics.AnimationExportSettings(3840,2160)
settings.TemporaryFramesPath=OUT+r'\native_frames'
System.IO.Directory.CreateDirectory(settings.TemporaryFramesPath)
System.IO.File.WriteAllText(OUT+r'\gpu.txt',str(o.AcceleratedAnimationWillBeUsed))
r.ExportAnimation(OUT+r'\native.mp4',GraphicsAnimationExportFormat.MP4,settings)

assert r.Maximum.Value==before
System.IO.File.WriteAllLines(OUT+r'\audit.txt',[unicode(r.ObjectState),unicode(r.Name),unicode(r.Maximum),str(list(r.Location.Ids)),str(c.SceneHeight),str(c.ViewVector),str(c.UpVector)])
System.IO.File.WriteAllText(OUT+r'\COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))

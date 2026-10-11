JOB={'name': 'random_fig05_assembly', 'analysis': 4269, 'result': 4316, 'camera': 'Back', 'maximum': 8.060016261879355e-05, 'title': 'Base Z | RMS response Z | Rear view', 'kind': 'rms', 'frequency': None}
OUT='Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\video_4k60_20261005_1928\\random_fig05_assembly'
import System,math
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsAnimationExportFormat,ViewOrientationType
flags=System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic
G=ExtAPI.Graphics
PREF=G.ViewOptions.ResultPreference
G.ViewOptions.ShowMesh=False;G.ViewOptions.ShowLogo=False;G.ViewOptions.ShowRuler=False
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

base=(c.ViewVector.X,c.ViewVector.Y,c.ViewVector.Z)
u=(c.UpVector.X,c.UpVector.Y,c.UpVector.Z)
n=math.sqrt(sum([x*x for x in u]));u=tuple([x/n for x in u])
dot=sum([base[k]*u[k] for k in range(3)])
cross=(u[1]*base[2]-u[2]*base[1],u[2]*base[0]-u[0]*base[2],u[0]*base[1]-u[1]*base[0])
for i in range(121):
 theta=-18*math.pi/180*math.cos(math.pi*i/120)
 vec=[base[k]*math.cos(theta)+cross[k]*math.sin(theta)+u[k]*dot*(1-math.cos(theta)) for k in range(3)]
 c.ViewVector=Ansys.ACT.Math.Vector3D(*vec)
 G.ExportImage(OUT+'\\frame_%04d.png'%i,GraphicsImageExportFormat.PNG,s)
 System.IO.File.WriteAllText(OUT+r'\progress.txt',str(i+1)+'/121')

assert r.Maximum.Value==before
System.IO.File.WriteAllLines(OUT+r'\audit.txt',[unicode(r.ObjectState),unicode(r.Name),unicode(r.Maximum),str(list(r.Location.Ids)),str(c.SceneHeight),str(c.ViewVector),str(c.UpVector)])
System.IO.File.WriteAllText(OUT+r'\COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))

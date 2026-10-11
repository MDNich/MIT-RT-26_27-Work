import System,math
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType
VROOT=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\video_4k60_20261005_1928'
rows=[]
flags=System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance
for n,o in [('legend',ExtAPI.Graphics.GlobalLegendSettings),('keyframes',ExtAPI.Graphics.KeyframeAnimationUtility)]:
 for f in o.GetType().GetFields(flags):
  if f.Name in ['_legend','_graphics','_keyframeAnimationUtility']:
   rows.append(n+' '+str(f.FieldType))
   for m in f.FieldType.GetMethods():rows.append(str(m))
System.IO.File.WriteAllLines(VROOT+r'\native_interfaces.txt',rows)
r=ExtAPI.DataModel.GetObjectById(4282);r.Activate()
c=ExtAPI.Graphics.Camera
c.ViewVector=Ansys.ACT.Math.Vector3D(1,-1,-1)
c.UpVector=Ansys.ACT.Math.Vector3D(-0.3,1,-1.3)
c.SetFit();c.SceneHeight=Quantity(str(c.SceneHeight.Value*1.35)+' [mm]')
s=Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
s.CurrentGraphicsDisplay=False;s.Width=3840;s.Height=2160;s.FontMagnification=3
start=System.DateTime.UtcNow
for i in range(8):
 a=math.pi*i/90
 c.ViewVector=Ansys.ACT.Math.Vector3D(math.cos(a)+math.sin(a),-math.cos(a)+math.sin(a),-1)
 ExtAPI.Graphics.ExportImage(VROOT+'\\orbit_test_%02d.png'%i,GraphicsImageExportFormat.PNG,s)
System.IO.File.WriteAllText(VROOT+r'\orbit_test_time.txt',str(System.DateTime.UtcNow-start))

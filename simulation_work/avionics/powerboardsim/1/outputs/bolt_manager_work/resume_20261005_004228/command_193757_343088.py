import System
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat
VROOT=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\video_4k60_20261005_1928'
s=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();s.Width=3840;s.Height=2160;s.CurrentGraphicsDisplay=False
r=ExtAPI.DataModel.GetObjectById(4207);r.Activate()
o=ExtAPI.Graphics.ResultAnimationOptions;o.NumberOfFrames=91
ac=o.GetType().GetField('_animationControl',System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic).GetValue(o)
ac.Play();ac.Pause()
rows=[]
for i,mag in [(0,0.7),(23,1.0),(45,1.5),(68,2.0)]:
 ac.FrameNumber=i
 s.FontMagnification=mag
 ExtAPI.Graphics.ExportImage(VROOT+'\\direct_modal_%02d.png'%i,GraphicsImageExportFormat.PNG,s)
 rows.append(str((i,mag,ac.FrameNumber,ac.NumberOfFrames,ac.AnimationStyle)))
ac.Stop()
System.IO.File.WriteAllLines(VROOT+r'\direct_modal_done.txt',rows)

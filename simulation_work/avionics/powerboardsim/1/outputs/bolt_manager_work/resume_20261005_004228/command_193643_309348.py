import System,math
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsAnimationExportFormat
VROOT=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\video_4k60_20261005_1928'
start=System.DateTime.UtcNow
s=Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
s.CurrentGraphicsDisplay=False;s.Width=3840;s.Height=2160;s.FontMagnification=1.5
ExtAPI.Graphics.GlobalLegendSettings.ShowDateAndTime=False
for i in range(4):
 ExtAPI.Graphics.ExportImage(VROOT+'\\bmp_test_%02d.bmp'%i,GraphicsImageExportFormat.BMP,s)
System.IO.File.WriteAllText(VROOT+r'\bmp_test_time.txt',str(System.DateTime.UtcNow-start))
gfx=ExtAPI.Graphics.GlobalLegendSettings.GetType().GetField('_graphics',System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic).GetValue(ExtAPI.Graphics.GlobalLegendSettings)
gfx.UpdateScreenFontSize(3.0)
r=ExtAPI.DataModel.GetObjectById(4189);r.Activate()
c=ExtAPI.Graphics.Camera
c.ViewVector=Ansys.ACT.Math.Vector3D(1,1,-1);c.UpVector=Ansys.ACT.Math.Vector3D(-1,2,1)
c.SetFit();c.SceneHeight=Quantity(str(c.SceneHeight.Value*1.3)+' [mm]')
o=ExtAPI.Graphics.ResultAnimationOptions;o.NumberOfFrames=5;o.Duration=Quantity(0.15,'s')
s2=Ansys.Mechanical.Graphics.AnimationExportSettings(3840,2160)
s2.TemporaryFramesPath=VROOT+r'\font_modal_frames'
System.IO.Directory.CreateDirectory(s2.TemporaryFramesPath)
r.ExportAnimation(VROOT+r'\font_modal.mp4',GraphicsAnimationExportFormat.MP4,s2)
System.IO.File.WriteAllText(VROOT+r'\font_modal_done.txt',str(System.DateTime.UtcNow))

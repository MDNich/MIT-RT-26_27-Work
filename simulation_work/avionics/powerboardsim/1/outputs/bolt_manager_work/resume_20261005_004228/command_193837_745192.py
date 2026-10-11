import System
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsAnimationExportFormat
VROOT=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\video_4k60_20261005_1928'
flags=System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic
o=ExtAPI.Graphics.ResultAnimationOptions
ac=o.GetType().GetField('_animationControl',flags).GetValue(o)
ac.Stop()
s=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();s.Width=3840;s.Height=2160;s.CurrentGraphicsDisplay=False
for i,mag in enumerate([0.7,1.0]):
 s.FontMagnification=mag
 ExtAPI.Graphics.ExportImage(VROOT+'\\font_still_%d.png'%i,GraphicsImageExportFormat.PNG,s)
gls=ExtAPI.Graphics.GlobalLegendSettings
gfx=gls.GetType().GetField('_graphics',flags).GetValue(gls)
gfx.SetFontStyle(0,'',0,0,48,0,0)
lg=gls.GetType().GetField('_legend',flags).GetValue(gls)
lg.IsFontSizeCustomized=True
r=ExtAPI.DataModel.GetObjectById(4207)
s2=Ansys.Mechanical.Graphics.AnimationExportSettings(3840,2160);s2.TemporaryFramesPath=VROOT+r'\font2_modal_frames'
System.IO.Directory.CreateDirectory(s2.TemporaryFramesPath)
o.NumberOfFrames=3;o.Duration=Quantity(0.07,'s')
r.ExportAnimation(VROOT+r'\font2_modal.mp4',GraphicsAnimationExportFormat.MP4,s2)
System.IO.File.WriteAllText(VROOT+r'\font2_done.txt',str(System.DateTime.UtcNow))

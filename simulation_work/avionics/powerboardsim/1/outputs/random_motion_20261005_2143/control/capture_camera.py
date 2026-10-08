import System
c=ExtAPI.Graphics.Camera
System.IO.File.WriteAllLines(r'C:\Temp\PBMotionVideos\random_fig15_pcb_baseX\camera_audit.txt',[str(c.SceneHeight),str(c.SceneWidth),str(c.ViewVector),str(c.UpVector),str(c.FocalPoint)])

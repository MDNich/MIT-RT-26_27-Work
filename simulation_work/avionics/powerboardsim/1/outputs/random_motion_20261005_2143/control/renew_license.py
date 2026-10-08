ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
import System
c=ExtAPI.Graphics.Camera
System.IO.File.WriteAllLines(r'C:\Temp\PBMotionVideos\random_fig17_pcb_baseZ\camera_audit.txt',[str(c.SceneHeight),str(c.SceneWidth),str(c.ViewVector),str(c.UpVector),str(c.FocalPoint)])

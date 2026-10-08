import System
c=ExtAPI.Graphics.Camera
p=c.FocalPoint
System.IO.File.WriteAllLines(pbmotionroot+r'\control\camera_type.txt',[str(p.GetType()),repr(p)]+[str(m) for m in p.GetType().GetConstructors()]+[str(m) for m in p.GetType().GetProperties()])

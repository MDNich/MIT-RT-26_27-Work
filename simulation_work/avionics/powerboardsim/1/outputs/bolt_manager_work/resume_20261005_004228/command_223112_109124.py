import System
pbflags=System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic
pbo=ExtAPI.Graphics.ResultAnimationOptions
pbf=pbo.GetType().GetField('_animationControl',pbflags)
pbc=pbf.GetValue(pbo)
pbl=[]
for pbn in ['ForwardBackwardMode','AnimationStyle','NumberOfFrames','FrameNumber','PlayLength','AcceleratedAnimationWillBeUsed']:
 try:pbl.append(pbn+'='+str(pbf.FieldType.GetProperty(pbn).GetValue(pbc,None)))
 except Exception as ex:pbl.append(pbn+': '+str(ex))
for pbp in pbo.GetType().GetProperties():
 try:pbl.append(str(pbp.Name)+'='+str(pbp.GetValue(pbo,None)))
 except:pass
System.IO.File.WriteAllLines(pbmotionroot+r'\control\animation_settings_now.txt',pbl)

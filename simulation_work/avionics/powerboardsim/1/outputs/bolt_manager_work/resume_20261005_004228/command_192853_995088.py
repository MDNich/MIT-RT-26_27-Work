import System
rows=[]
for obj,label in [(ExtAPI.Graphics.KeyframeAnimationUtility,'keyframe'),(ExtAPI.Graphics.ResultAnimationOptions,'animation'),(ExtAPI.Graphics.ViewOptions,'view')]:
 rows.append('TYPE '+label+' '+obj.GetType().FullName)
 for p in obj.GetType().GetProperties():rows.append('P '+unicode(p)+' write='+str(p.CanWrite))
 for method in obj.GetType().GetMethods():
  if not method.Name.startswith(('get_','set_')):rows.append('M '+unicode(method))
rows.append('Graphics.AcceleratedGraphics '+unicode(ExtAPI.Graphics.AcceleratedGraphics))
rows.append('Graphics.AdvancedRenderingIsSupported '+unicode(ExtAPI.Graphics.AdvancedRenderingIsSupported))
System.IO.File.WriteAllLines(PCB670_RUN+r'\keyframe_api_probe.txt',rows)

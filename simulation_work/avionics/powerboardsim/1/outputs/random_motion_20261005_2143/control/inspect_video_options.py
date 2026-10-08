import System
r=ExtAPI.DataModel.GetObjectById(4571)
rows=[]
for obj in [r,ExtAPI.Graphics.GlobalLegendSettings,ExtAPI.Graphics.ResultAnimationOptions]:
 rows.append(unicode(obj.GetType()))
 for p in obj.GetType().GetProperties():
  if any(x in p.Name.lower() for x in ['font','time','legend','range','min','max','frame']):
   try:rows.append(p.Name+'='+unicode(p.GetValue(obj,None)))
   except:rows.append(p.Name)
System.IO.File.WriteAllLines(pbmotionroot+r'\control\video_options.txt',rows)

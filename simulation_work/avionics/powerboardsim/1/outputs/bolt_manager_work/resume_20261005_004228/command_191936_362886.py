import System
rows=['UTC '+System.DateTime.UtcNow.ToString('o')]
r=ExtAPI.DataModel.GetObjectById(4207)
for obj,label in [(r,'result'),(ExtAPI.Graphics,'graphics'),(ExtAPI.Graphics.ViewOptions.ResultPreference,'pref'),(ExtAPI.Graphics.Camera,'camera')]:
 rows.append(label+' '+obj.GetType().FullName)
 for p in obj.GetType().GetProperties():
  if label in ['pref','camera'] or any(s in p.Name.lower() for s in ['anim','scale','phase']):rows.append('P '+unicode(p)+' write='+str(p.CanWrite))
 for method in obj.GetType().GetMethods():
  if any(s in method.Name.lower() for s in ['anim','export']):rows.append('M '+unicode(method))
rows.append('GraphicsTypes '+', '.join(dir(Ansys.Mechanical.Graphics)))
for aid in [1656,4182,4259,4264,4269]:
 a=ExtAPI.DataModel.GetObjectById(aid);rows.append('ANALYSIS '+str(aid)+' '+a.Name+' '+unicode(a.Solution.ObjectState)+' '+a.SystemCaption)
System.IO.File.WriteAllLines(PCB670_RUN+r'\animation_api_probe.txt',rows)

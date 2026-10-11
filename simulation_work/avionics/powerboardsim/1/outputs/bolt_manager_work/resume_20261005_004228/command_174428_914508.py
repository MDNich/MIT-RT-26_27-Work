
import System
out=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_vibration_20261005_0950\battery_oblique_camera_probe.txt'
rows=[]
for obj in [ExtAPI.Graphics.Camera,ExtAPI.Graphics.ViewOptions.ResultPreference]:
 rows.append('TYPE '+unicode(obj.GetType()))
 for p in obj.GetType().GetProperties():
  try:rows.append(p.Name+'|'+unicode(p.PropertyType)+'|'+unicode(p.GetValue(obj,None)))
  except:pass
for oid in [4259,4264,4269]:
 a=ExtAPI.DataModel.GetObjectById(oid)
 rows.append('ANALYSIS '+str(oid)+' '+unicode(a.Solution.ObjectState))
 for o in a.Solution.Children:
  if hasattr(o,'Maximum') and unicode(o.Name).startswith('RMS displacement'):
   rows.append('RESULT '+str(o.ObjectId)+'|'+unicode(o.Name)+'|'+unicode(o.Maximum)+'|'+unicode(o.Location))
System.IO.File.WriteAllText(out,'\n'.join(rows))

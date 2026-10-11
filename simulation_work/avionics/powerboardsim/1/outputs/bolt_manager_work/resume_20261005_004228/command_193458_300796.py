import System
VROOT=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\video_4k60_20261005_1928'
rows=[]
for n,o in [('annotations',ExtAPI.Graphics.ViewOptions.AnnotationPreferences),('legend',ExtAPI.Graphics.GlobalLegendSettings),('settings',Ansys.Mechanical.Graphics.GraphicsImageExportSettings()),('keyframes',ExtAPI.Graphics.KeyframeAnimationUtility)]:
 rows.append(n+' '+str(o.GetType()))
 for p in o.GetType().GetProperties():
  try: rows.append('P '+str(p)+' = '+str(p.GetValue(o,None)))
  except: rows.append('P '+str(p))
 for m in o.GetType().GetMethods():
  if not m.IsSpecialName:rows.append('M '+str(m))
 for f in o.GetType().GetFields(System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance):
  rows.append('F '+str(f))
System.IO.File.WriteAllLines(VROOT+r'\annotation_probe.txt',rows)

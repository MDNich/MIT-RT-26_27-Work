import System
VROOT=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\video_4k60_20261005_1928'
flags=System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic
rows=[]
for o in [ExtAPI.Graphics.ResultAnimationOptions,ExtAPI.Graphics.ViewOptions.ResultPreference]:
 rows.append(str(o.GetType()))
 for f in o.GetType().GetFields(flags):
  rows.append(str(f))
  if 'anim' in f.Name.lower() or 'result' in f.Name.lower():
   for m in f.FieldType.GetMethods():rows.append(str(m))
System.IO.File.WriteAllLines(VROOT+r'\modal_frames_probe.txt',rows)
gfx=ExtAPI.Graphics.GlobalLegendSettings.GetType().GetField('_graphics',flags).GetValue(ExtAPI.Graphics.GlobalLegendSettings)
gfx.UpdateScreenFontSize(1.0)

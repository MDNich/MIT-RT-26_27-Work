
c=ExtAPI.Graphics.Camera
lines=[]
for p in c.GetType().GetProperties():
 lines.append(p.Name+' writable='+str(p.CanWrite))
for method in c.GetType().GetMethods():
 if any(k in method.Name.lower() for k in ['zoom','pan','fit','scene']):lines.append(unicode(method))
System.IO.File.WriteAllText(r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_vibration_20261005_0950\battery_camera_api.txt','\n'.join(lines))

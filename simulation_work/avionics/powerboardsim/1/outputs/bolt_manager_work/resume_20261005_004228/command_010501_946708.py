# Record camera settings so the report can use a clear battery-side view.
ls=[]
for p in ExtAPI.Graphics.Camera.GetType().GetProperties():
 try:ls.append(p.Name+' '+unicode(p.GetValue(ExtAPI.Graphics.Camera,None))+' '+unicode(p.PropertyType))
 except:pass
System.IO.File.WriteAllText(PCB670_RUN+r'\camera_api.txt',u'\n'.join(ls))

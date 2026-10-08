s=[]
s.append('Application licensing APIs')
for m in ExtAPI.Application.GetType().GetMethods():
 if any(x in m.Name.lower() for x in ['licen','active','enviro','readonly']):s.append(unicode(m))
s.append('new analysis internal methods')
for m in rvmodal.InternalObject.GetType().GetMethods():
 if any(x in m.Name.lower() for x in ['licen','active','enviro','readonly']):s.append(unicode(m))
for msg in ExtAPI.Application.Messages:
 try:s.append('MESSAGE '+unicode(msg.Severity)+' '+unicode(msg.DisplayString))
 except:s.append(unicode(msg))
System.IO.File.WriteAllText(RV_ROOT+r'\license_probe.txt','\n'.join(s))
cmd="""import System
s=[]
for x in GetAllSystems():
 s.append(x.Name+' | '+x.DisplayText)
System.IO.File.WriteAllText(r'%s\\workbench_systems.txt','\\n'.join(s))
"""%RV_ROOT
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync(cmd)

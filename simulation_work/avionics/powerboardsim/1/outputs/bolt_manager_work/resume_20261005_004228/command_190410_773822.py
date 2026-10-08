import System
rows=[]
for aid in [1656,4182,4254,4259,4264,4269]:
 a=ExtAPI.DataModel.GetObjectById(aid)
 rows.append(str(aid)+' '+unicode(a.SystemCaption))
for p in a.GetType().GetProperties():
 if any(k in p.Name.lower() for k in ['caption','title','system']):rows.append(unicode(p)+' writable='+str(p.CanWrite))
System.IO.File.WriteAllLines(OUT+r'\caption_probe.txt',rows)
cmd="""import System
s=[]
for x in GetAllSystems():
 s.append(x.Name+' | '+x.DisplayText)
System.IO.File.WriteAllText(r'%s\\workbench_systems.txt','\\n'.join(s))
"""%OUT
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync(cmd)

cmd="""import System
s=[]
for x in GetAllSystems():
 try:
  co=x.GetComponent(Name='Model')
  s.append(x.Name+' | '+x.DisplayText+' | '+unicode(co.DirectoryName))
 except Exception as e:s.append(x.Name+' ERR '+unicode(e))
System.IO.File.WriteAllText(r'%s\\workbench_system_dirs.txt','\\n'.join(s))
"""%RV_ROOT
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync(cmd)

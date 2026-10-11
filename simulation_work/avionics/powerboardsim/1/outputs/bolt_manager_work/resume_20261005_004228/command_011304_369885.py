ls=[]
o=ExtAPI.DataModel.GetObjectById(3896)
for p in o.GetType().GetProperties():
 if any(k in p.Name for k in ['Behavior','Detection','Formulation']):
  ls.append(p.Name+' '+str(p.PropertyType))
  if p.PropertyType.IsEnum:ls.extend([str(x) for x in System.Enum.GetValues(p.PropertyType)])
System.IO.File.WriteAllText(PCB670_RUN+r'\contact_enums.txt','\n'.join(ls))

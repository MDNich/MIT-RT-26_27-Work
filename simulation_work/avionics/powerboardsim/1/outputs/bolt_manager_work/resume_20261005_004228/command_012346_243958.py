ls=['MESH TYPE '+str(m.Mesh.GetType())]
for o in [m.Mesh]+list(m.Mesh.Children):
 ls.append(str(o.ObjectId)+' '+o.Name+' '+str(o.GetType()))
 for p in o.VisibleProperties:
  try:ls.append(p.Name+'='+unicode(p.InternalValue))
  except:pass
System.IO.File.WriteAllText(PCB670_RUN+r'\mesh_controls.txt','\n'.join(ls))

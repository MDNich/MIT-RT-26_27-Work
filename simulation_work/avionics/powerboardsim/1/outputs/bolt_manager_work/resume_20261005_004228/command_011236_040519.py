ls=[]
for oid in [3896,4049]:
 o=ExtAPI.DataModel.GetObjectById(oid)
 ls.append(str(oid)+' '+o.Name)
 for p in o.VisibleProperties:
  try:ls.append(p.Name+'='+unicode(p.InternalValue))
  except:pass
System.IO.File.WriteAllText(PCB670_RUN+r'\pivot_contact_details.txt','\n'.join(ls))

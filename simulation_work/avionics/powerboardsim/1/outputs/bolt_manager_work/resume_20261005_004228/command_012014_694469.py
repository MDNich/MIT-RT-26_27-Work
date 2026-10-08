mesh=ExtAPI.DataModel.MeshDataByName('Global');ls=[]
for nid in [18391,84142]:
 n=mesh.NodeById(nid);ls.append('NODE '+str(nid)+' '+str(n.X)+','+str(n.Y)+','+str(n.Z))
 for b in m.Geometry.GetChildren(DataModelObjectCategory.Body,True):
  gb=b.GetGeoBody()
  try:
   if nid in list(mesh.MeshRegionById(gb.Id).NodeIds):ls.append('BODY '+str(gb.Id)+' '+b.Name)
  except:pass
System.IO.File.WriteAllText(PCB670_RUN+r'\pivot_owners2.txt','\n'.join(ls))

mesh=ExtAPI.DataModel.MeshDataByName('Global')
ls=[]
for nid in [2361,3379]:
 n=mesh.NodeById(nid)
 ls.append('NODE '+str(nid)+' '+str(n.X)+','+str(n.Y)+','+str(n.Z))
 for b in ExtAPI.DataModel.Project.Model.Geometry.GetChildren(DataModelObjectCategory.Body,True):
  gb=b.GetGeoBody()
  try:
   if nid in list(mesh.MeshRegionById(gb.Id).NodeIds):ls.append('BODY '+str(gb.Id)+' '+b.Name)
  except:pass
System.IO.File.WriteAllText(PCB670_RUN+r'\pivot_owners.txt','\n'.join(ls))

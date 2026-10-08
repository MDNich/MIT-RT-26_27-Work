ls=[]
for gid in [42342,20040,20246,20466,20407,20878,20356,23149]:
 try:
  b=ExtAPI.DataModel.GeoData.GeoEntityById(gid);ls.append('BODY '+str(gid)+' '+str(b.Name))
  for f in b.Faces:
   if str(f.SurfaceType)=='GeoSurfacePlane':ls.append('FACE '+str(f.Id)+' '+str(list(f.Centroid))+' area='+str(f.Area))
 except Exception as x:ls.append(str(x))
mesh=ExtAPI.DataModel.MeshDataByName('Global')
for nid in [1391,51280]:
 n=mesh.NodeById(nid);ls.append('NODE '+str(nid)+' '+str(n.X)+','+str(n.Y)+','+str(n.Z))
 for b in m.Geometry.GetChildren(DataModelObjectCategory.Body,True):
  gb=b.GetGeoBody()
  try:
   if nid in list(mesh.MeshRegionById(gb.Id).NodeIds):ls.append('BODY '+str(gb.Id)+' '+b.Name)
  except:pass
System.IO.File.WriteAllText(PCB670_RUN+r'\bearing_faces.txt','\n'.join(ls))
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')

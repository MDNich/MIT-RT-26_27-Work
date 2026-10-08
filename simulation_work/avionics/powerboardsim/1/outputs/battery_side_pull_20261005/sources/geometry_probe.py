import System
PULLROOT = r"Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\battery_side_pull_20261005"
rows=[]
for b in Model.Geometry.GetChildren(DataModelObjectCategory.Body,True):
 g=b.GetGeoBody()
 if g.Id<20000:continue
 rows.append('BODY\t'+str(b.ObjectId)+'\t'+str(g.Id)+'\t'+b.Name+'\t'+str(b.Material))
 for f in g.Faces:
  rows.append('FACE\t'+str(g.Id)+'\t'+str(f.Id)+'\t'+str(f.SurfaceType)+'\t'+str(f.Area)+'\t'+str(list(f.Centroid)))
  for e1 in f.Edges:
   for v in e1.Vertices:
    rows.append('VERTEX\t'+str(g.Id)+'\t'+str(v.Id)+'\t'+str([v.X,v.Y,v.Z]))
for c in Model.Connections.GetChildren(DataModelObjectCategory.ContactRegion,True):
 if c.ObjectId<1775 or c.ObjectId>4170:
  rows.append('CONTACT\t'+str(c.ObjectId)+'\t'+str(c.Suppressed)+'\t'+str(c.ContactType)+'\t'+str(list(c.SourceLocation.Ids))+'\t'+str(list(c.TargetLocation.Ids)))
System.IO.File.WriteAllText(PULLROOT+r'\audit\geometry_probe.tsv','\n'.join(rows))
System.IO.File.WriteAllText(PULLROOT+r'\audit\static_api.txt','\n'.join(dir(ExtAPI.DataModel.GetObjectById(4123))))

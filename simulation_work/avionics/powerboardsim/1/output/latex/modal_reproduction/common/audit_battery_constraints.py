import System
m=ExtAPI.DataModel.Project.Model
batteries=set([20157,20675,20822]);nickel=set([20091,20297,20348,20642,20756,20929])
def walk(o):
 for c in getattr(o,'Children',[]):
  yield c
  for d in walk(c):yield d
objects=list(walk(m));bodies=[o for o in objects if unicode(getattr(o,'DataModelObjectCategory',''))=='Body' and not o.Suppressed]
owner={}
for b in bodies:
 g=b.GetGeoBody();owner[g.Id]=g.Id
 for f in g.Faces:owner[f.Id]=g.Id
records=[];allowed=[]
for c in objects:
 if unicode(getattr(c,'DataModelObjectCategory',''))!='ContactRegion' or c.Suppressed:continue
 src=set(owner.get(i,-1) for i in c.SourceLocation.Ids);dst=set(owner.get(i,-1) for i in c.TargetLocation.Ids)
 for a in src:
  for b in dst:
   records.append((c.ObjectId,a,b,unicode(c.ContactType)))
   if a in batteries or b in batteries:
    assert (a in batteries and b in nickel) or (b in batteries and a in nickel),unicode((c.ObjectId,a,b))
    allowed.append((c.ObjectId,a,b))
assert len(allowed)==6,unicode(allowed)
mesh=ExtAPI.DataModel.MeshDataByName('Global')
batnodes=dict((b,set(mesh.MeshRegionById(b).NodeIds)) for b in batteries)
shared=[]
for body in bodies:
 gid=body.GetGeoBody().Id
 if gid in batteries or gid in nickel:continue
 nodes=set(mesh.MeshRegionById(gid).NodeIds)
 for bid in batteries:
  common=nodes.intersection(batnodes[bid])
  assert not common,'Battery shares nodes with body '+unicode(gid)
System.IO.File.WriteAllText(PCB670_RUN+r'\battery_connection_audit.txt','Verified six battery-to-nickel contacts, no direct battery-to-PCB or other contacts, and no shared mesh nodes with bodies other than nickel.\n'+unicode(allowed))
System.IO.File.WriteAllText(PCB670_RUN+r'\final_active_contacts.tsv',u'\n'.join(u'\t'.join(unicode(x) for x in row) for row in records))

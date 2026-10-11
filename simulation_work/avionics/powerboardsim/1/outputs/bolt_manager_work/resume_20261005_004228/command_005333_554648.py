# Read-only contact and material inventory for the comparison report.
import System
m=ExtAPI.DataModel.Project.Model
def walk(o):
 for c in getattr(o,'Children',[]):
  yield c
  for d in walk(c):yield d
objs=list(walk(m));bodies=[o for o in objs if unicode(getattr(o,'DataModelObjectCategory',''))=='Body'];owner={};bl=[]
for b in bodies:
 g=b.GetGeoBody();owner[g.Id]=g.Id
 for f in g.Faces:owner[f.Id]=g.Id
 bl.append(unicode(g.Id)+'\t'+unicode(b.Name)+'\t'+unicode(b.Material)+'\t'+unicode(b.Suppressed))
cl=[]
for c in objs:
 if unicode(getattr(c,'DataModelObjectCategory',''))!='ContactRegion':continue
 try:
  x=sorted(set(owner.get(i,-1) for i in c.SourceLocation.Ids));y=sorted(set(owner.get(i,-1) for i in c.TargetLocation.Ids))
  cl.append(unicode(c.ObjectId)+'\t'+unicode(c.Suppressed)+'\t'+unicode(c.ContactType)+'\t'+unicode(x)+'\t'+unicode(y))
 except:cl.append('error '+unicode(c.ObjectId))
System.IO.File.WriteAllText(PCB670_RUN+r'\bodies.tsv',u'\n'.join(bl),System.Text.UTF8Encoding(False))
System.IO.File.WriteAllText(PCB670_RUN+r'\contacts.tsv',u'\n'.join(cl),System.Text.UTF8Encoding(False))
# Native API inventory for graphics and result extraction, no model changes.
ls=[]
for target in [ExtAPI.Graphics,ExtAPI.Graphics.Camera,baseline.GetResultsData(),baseline.Solution.Children[-1]]:
 ls.append(unicode(target.GetType()))
 ls.extend(unicode(m) for m in target.GetType().GetMethods() if any(t in m.Name.lower() for t in ['export','freq','listtime','fit','orient','camera','scale','result']))
 ls.extend(unicode(p) for p in target.GetType().GetProperties() if any(t in p.Name.lower() for t in ['freq','time','mode','camera','scale','result']))
System.IO.File.WriteAllText(PCB670_RUN+r'\result_api.txt',u'\n'.join(ls))

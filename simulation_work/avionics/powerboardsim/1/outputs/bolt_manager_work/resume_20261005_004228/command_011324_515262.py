# Keep component faces as the constrained side of their existing PCB bonds.
from Ansys.Mechanical.DataModel.Enums import ContactBehavior,ContactFormulation,ContactDetectionPoint
case=PCB670_RUN+r'\bolted750_asymmetric'
System.IO.Directory.CreateDirectory(case)
changes=[]
for o in m.Connections.GetChildren(DataModelObjectCategory.ContactRegion,True):
 if not o.Suppressed and o.SourceLocation is not None and o.TargetLocation is not None:
  sb=set();tb=set()
  for x in o.SourceLocation.Ids:
   g=ExtAPI.DataModel.GeoData.GeoEntityById(x)
   try:sb.add(g.Body.Id)
   except:pass
  for x in o.TargetLocation.Ids:
   g=ExtAPI.DataModel.GeoData.GeoEntityById(x)
   try:tb.add(g.Body.Id)
   except:pass
  if tb==set([42342]) and len(sb)==1 and list(sb)[0]<20000:
   changes.append(str(o.ObjectId)+'\t'+str(o.Behavior)+'\t'+str(o.ContactFormulation)+'\t'+str(o.DetectionMethod))
   o.Behavior=ContactBehavior.Asymmetric
   o.ContactFormulation=ContactFormulation.MPC
   o.DetectionMethod=ContactDetectionPoint.NodalNormalToTarget
System.IO.File.WriteAllText(case+r'\contact_changes.tsv','\n'.join(changes))
assert len(changes)==172,str(len(changes))
bm.StartApdlInputFileWrite(static)
static.WriteInputFile(case+r'\static_input.dat')

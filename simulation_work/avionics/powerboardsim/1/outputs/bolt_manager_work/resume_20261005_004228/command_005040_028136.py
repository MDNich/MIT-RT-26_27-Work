e=[e for e in ExtAPI.ExtensionManager.Extensions if e.Name=='BoltTools'][0]
manager=[o for o in ExtAPI.DataModel.GetUserObjects(e) if o.Name=='ApdlBoltManager'][0]
lines=[]
for obj in [manager,list(manager.Children)[0]]:
 mech=obj.Controller.GetMechanicalObj()
 lines.append('OBJ '+unicode(mech.ObjectId)+' '+unicode(mech.Name))
 for p in mech.GetType().GetProperties():
  if any(x in p.Name.lower() for x in ['suppress','analysis','valid','state','status']):
   try:lines.append(p.Name+'='+unicode(p.GetValue(mech,None)))
   except:pass
 lines.append('ATTR '+unicode(list(obj.Attributes.Keys)))
System.IO.File.WriteAllText(PCB670_RUN+r'\bolt_scope_api.txt',u'\n'.join(lines))

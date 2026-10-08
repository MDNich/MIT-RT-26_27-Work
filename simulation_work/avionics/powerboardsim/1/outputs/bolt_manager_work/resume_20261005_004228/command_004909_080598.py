import System,traceback
m=ExtAPI.DataModel.Project.Model
lines=[]
for a in m.Analyses:
 lines.append('ANALYSIS '+unicode(a.ObjectId)+' '+unicode(a.Name))
 for p in a.AnalysisSettings.GetType().GetProperties():
  if any(x in p.Name.lower() for x in ['mode','frequency','damp','solver','range','step']):
   try:lines.append(p.Name+'='+unicode(p.GetValue(a.AnalysisSettings,None))+' TYPE='+unicode(p.PropertyType))
   except:pass
 for c in a.Children:
  if 'Support' in unicode(c.DataModelObjectCategory):lines.append('SUPPORT '+unicode(c.ObjectId)+' '+unicode(c.Location.Ids)+' suppressed='+unicode(c.Suppressed))
e=[e for e in ExtAPI.ExtensionManager.Extensions if e.Name=='BoltTools'][0]
for o in ExtAPI.DataModel.GetUserObjects(e):
 lines.append('BOLT '+unicode(o.Name)+' '+unicode(o.Id))
 for p in o.Properties:
  try:lines.append('  '+unicode(p.Name)+'='+unicode(p.Value))
  except:pass
 try:lines.append('DATA '+unicode(o.Controller.GetData()))
 except:pass
System.IO.File.WriteAllText(PCB670_RUN+r'\settings_api.txt',u'\n'.join(lines),System.Text.UTF8Encoding(False))

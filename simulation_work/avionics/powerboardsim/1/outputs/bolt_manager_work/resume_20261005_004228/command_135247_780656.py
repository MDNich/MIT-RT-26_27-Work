rvmodal=ExtAPI.DataModel.GetObjectById(4254)
s=[]
for o in [rvmodal,rvmodal.AnalysisSettings]+[x for x in rvmodal.Children if unicode(x.DataModelObjectCategory)=='InitialCondition']:
 s.append('OBJECT '+unicode(o.GetType().FullName))
 for p in o.GetType().GetProperties():
  try:s.append('%s|%s|%s'%(p.Name,p.PropertyType.FullName,p.GetValue(o,None)))
  except:pass
 for p in o.VisibleProperties:
  try:s.append('VISIBLE %s | %s | %s | %s'%(p.Name,p.APIName,p.Value,p.ReadOnly))
  except Exception as e:s.append('prop '+unicode(p.Name)+' '+unicode(e))
System.IO.File.WriteAllText(RV_ROOT+r'\new_modal_probe.txt','\n'.join(s))

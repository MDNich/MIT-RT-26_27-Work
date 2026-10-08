s=[]
for a in rvs:
 s.append('ANALYSIS '+unicode(a.ObjectId)+' '+unicode(a.ObjectState))
 for o in a.Solution.Children:
  s.append('RESULT '+unicode(o.ObjectId)+' '+unicode(o.Name)+' '+unicode(o.DataModelObjectCategory))
  if unicode(o.DataModelObjectCategory) not in ['DirectionalDeformation','DirectionalAcceleration']:continue
  for p in o.GetType().GetProperties():
   if any(k in p.Name.lower() for k in ['orientation','factor','aver','scale','unit','location','scope','acceleration','display']):
    try:s.append('%s|%s|%s'%(p.Name,p.PropertyType.FullName,p.GetValue(o,None)))
    except:pass
System.IO.File.WriteAllText(RV_ROOT+r'\result_probe.txt','\n'.join(s))

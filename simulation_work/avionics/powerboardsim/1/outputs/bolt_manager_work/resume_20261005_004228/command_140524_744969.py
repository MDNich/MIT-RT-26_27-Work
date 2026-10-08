s=[]
for o in [rvmodal.AnalysisSettings,rvs[0].AnalysisSettings]:
 s.append('SETTINGS '+unicode(o.Parent.ObjectId))
 for p in o.VisibleProperties:
  s.append('%s | %s | %s | readonly=%s | valid=%s'%(p.Name,p.APIName,p.InternalValue,p.ReadOnly,p.IsValid))
for n in ['ConstantDamping','DampingRatio','ConstantDampingRatio']:
 try:s.append(n+' = '+unicode(getattr(rvs[0].AnalysisSettings,n)))
 except:pass
System.IO.File.WriteAllText(RV_ROOT+r'\visible_settings.txt','\n'.join(s))

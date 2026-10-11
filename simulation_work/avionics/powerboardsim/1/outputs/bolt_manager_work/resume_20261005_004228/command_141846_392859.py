ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
s=[]
for m in rvs[0].Solution.GetType().GetMethods():
 if 'Stress' in m.Name or 'Strain' in m.Name or 'PSD' in m.Name:s.append(unicode(m))
for a in [rvmodal]+rvs:
 s.append('ANALYSIS '+unicode(a.ObjectId)+' '+unicode(a.ObjectState))
 for ch in a.Children:s.append('CHILD '+unicode(ch.ObjectId)+' '+unicode(ch.Name)+' '+unicode(ch.ObjectState))
System.IO.File.WriteAllText(RV_ROOT+r'\result_methods.txt','\n'.join(s))

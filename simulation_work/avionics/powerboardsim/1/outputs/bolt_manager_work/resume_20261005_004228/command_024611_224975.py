execfile(PCB670_RUN+r'\audit_battery_constraints.py')
static=ExtAPI.DataModel.GetObjectById(4123)
static.Solution.EvaluateAllResults()
ls=[]
for res in list(static.Solution.Children):
 if hasattr(res,'Maximum'):ls.append(unicode(res.Name)+' '+unicode(res.Maximum)+' '+unicode(res.Minimum))
System.IO.File.WriteAllText(PCB670_RUN+r'\bolted750_refined\static_result_summary.txt',u'\n'.join(ls))
pre=ExtAPI.DataModel.GetObjectById(1659)
System.IO.File.WriteAllText(PCB670_RUN+r'\bolted750_modal\prestress_properties.txt',u'\n'.join(unicode(p.Name)+'='+unicode(p.GetValue(pre,None)) for p in pre.GetType().GetProperties() if p.CanRead and any(x in p.Name.lower() for x in ['time','load','stress','restart'])))

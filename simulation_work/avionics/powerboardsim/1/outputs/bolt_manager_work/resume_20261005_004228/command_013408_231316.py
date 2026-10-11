REPORT_CASE='default_refined';REPORT_ANALYSIS_ID=4182
execfile(PCB670_RUN+r'\export_modal_results.py')
ls=[]
for o in [static.AnalysisSettings,ExtAPI.DataModel.GetObjectById(1696)]:
 for p in o.GetType().GetProperties():
  if any(k in p.Name for k in ['Substep','Stepping','StepNumber','Pinball','InterfaceTreatment','TrimContact','LargeDeflection']):
   ls.append(p.Name+' '+str(p.PropertyType))
   if p.PropertyType.IsEnum:ls.extend([str(x) for x in System.Enum.GetValues(p.PropertyType)])
System.IO.File.WriteAllText(PCB670_RUN+r'\bearing_setup_api.txt','\n'.join(ls))

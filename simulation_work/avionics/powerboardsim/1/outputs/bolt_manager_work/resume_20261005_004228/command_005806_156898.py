lines=[]
for a in [baseline,bolted]:
 lines.append(a.Name)
 for p in a.AnalysisSettings.GetType().GetProperties():
  if any(x in p.Name.lower() for x in ['contact','split','weak','pivot','solver']):
   try:lines.append(p.Name+'='+unicode(p.GetValue(a.AnalysisSettings,None)))
   except:pass
System.IO.File.WriteAllText(PCB670_RUN+r'\modal_differences.txt',u'\n'.join(lines))

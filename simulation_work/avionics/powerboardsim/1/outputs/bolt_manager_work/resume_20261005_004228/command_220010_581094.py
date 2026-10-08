with open(pbmotionroot+r'\control\animation_export_probe.txt','w') as f:
 pbs=Ansys.Mechanical.Graphics.AnimationExportSettings(3840,2160)
 for p in pbs.GetType().GetProperties():
  try:f.write(str(p.Name)+'='+str(p.GetValue(pbs,None))+'\n')
  except:pass

pba=ExtAPI.DataModel.GetObjectById(4559);pbl=[]
for pbp in pba.AnalysisSettings.GetType().GetProperties():
 if any(s in pbp.Name.lower() for s in ['solut','expan','solver','modal','result','store']):
  try:pbl.append(pbp.Name+'='+unicode(pbp.GetValue(pba.AnalysisSettings,None))+' TYPE '+unicode(pbp.PropertyType))
  except:pass
System.IO.File.WriteAllLines(pbmotionroot+r'\pilot_expand_nodal\settings_api.txt',pbl)

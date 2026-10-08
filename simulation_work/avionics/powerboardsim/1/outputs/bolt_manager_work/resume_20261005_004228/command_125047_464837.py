pba=ExtAPI.DataModel.GetObjectById(4559)
pbl=[]
for pbi in pba.InitialConditions:
 pbl.append(str(pbi.ObjectId)+' '+str(pbi.Name))
 for pbp in pbi.GetType().GetProperties():
  if any(s in pbp.Name for s in ['Modal','Type','Environment']):
   try:pbl.append(pbp.Name+'='+str(pbp.GetValue(pbi,None)))
   except:pass
System.IO.File.WriteAllLines(pbmotionroot+r'\pilot_expand_nodal\initial_condition_api.txt',pbl)

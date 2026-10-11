pbl=[]
for pbid in [4278,4289,4335,4348,4361]:
 pbr=ExtAPI.DataModel.GetObjectById(pbid)
 pbl.append(str(pbid)+' '+str(pbr.Name)+' '+str(list(pbr.Location.Ids)))
System.IO.File.WriteAllLines(pbmotionroot+r'\control\source_scopes.txt',pbl)

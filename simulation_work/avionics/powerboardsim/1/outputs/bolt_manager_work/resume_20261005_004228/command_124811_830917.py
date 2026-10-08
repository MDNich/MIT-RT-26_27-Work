pbr=ExtAPI.DataModel.GetObjectById(4566)
pbp=pbr.GetType().GetProperty('By')
pbl=list(System.Enum.GetNames(pbp.PropertyType))
for pbm in ExtAPI.Application.Messages:
 try:pbl.append(str(pbm.DisplayString))
 except:pbl.append(str(pbm))
System.IO.File.WriteAllLines(pbmotionroot+r'\pilot_expand_nodal\driver_options.txt',pbl)

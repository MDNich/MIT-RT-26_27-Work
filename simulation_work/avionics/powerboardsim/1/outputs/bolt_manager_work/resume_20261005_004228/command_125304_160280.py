pba=ExtAPI.DataModel.GetObjectById(4559);pbr=ExtAPI.DataModel.GetObjectById(4566)
pbl=['IC='+unicode(pba.InitialConditions[0].ModalEnvironmentTransientMSUPIC),'A='+unicode(pba.ObjectState),'S='+unicode(pba.Solution.ObjectState),'R='+unicode(pbr.ObjectState),'WorkingDir='+unicode(pba.WorkingDir)]
for pbo in [pba,pba.Solution,pbr]:
 for pbp in pbo.Properties:
  if any(s in unicode(pbp.Name).lower() for s in ['file','error','valid','state','result','read','time','modal','solution']):
   try:pbl.append(unicode(pbo.ObjectId)+' '+unicode(pbp.Name)+'='+unicode(pbp.InternalValue))
   except:pass
System.IO.File.WriteAllLines(pbmotionroot+r'\pilot_expand_nodal\evaluation_diagnostic.txt',pbl)

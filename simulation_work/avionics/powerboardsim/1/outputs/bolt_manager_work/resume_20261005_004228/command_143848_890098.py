ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
assert System.IO.File.Exists(RV_ROOT+r'\modal_basis\MODAL_VERIFIED.txt')
assert unicode(rvmodal.Solution.ObjectState)=='Solved'
unused=ExtAPI.DataModel.GetObjectById(4284)
if unused is not None:unused.Delete()
lines=[]
rvids=[]
for a,axis,icid in zip(rvs,['X','Y','Z'],[4262,4267,4272]):
 case=System.IO.Path.Combine(RV_ROOT,axis)
 System.IO.Directory.CreateDirectory(case)
 for component in ['X','Y','Z']:
  for kind in ['u','a']:
   result=a.Solution.AddDirectionalDeformation() if kind=='u' else a.Solution.AddDirectionalAccelerationPSD()
   result.Name='PCB RMS %s %s - base %s'%('displacement' if kind=='u' else 'absolute acceleration',component,axis)
   rv_enum(result,'NormalOrientation',component+'Axis')
   sel=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
   sel.Ids=[42342]
   result.Location=sel
   if kind=='a':result.AccelerationInG=True
   rvids.append('%s,%s,%s,%s'%(axis,kind,component,result.ObjectId))
 assert ExtAPI.DataModel.GetObjectById(icid).ModalEnvironmentPSDIC.ObjectId==4254
 assert abs(a.AnalysisSettings.ConstantDampingRatio-0.02)<1e-10
 assert not a.AnalysisSettings.ExcludeInsignificantModes
 bm.StartApdlInputFileWrite(a)
 a.WriteInputFile(System.IO.Path.Combine(case,'psd_input.dat'))
 lines.append('%s|%s|%s|%s'%(axis,a.ObjectId,a.WorkingDir,a.Solution.ObjectState))
System.IO.File.WriteAllText(RV_ROOT+r'\psd_inputs_exported.txt','\n'.join(lines))

System.IO.File.WriteAllText(RV_ROOT+r'\pcb_result_ids.csv','case,quantity,component,result_id\n'+'\n'.join(rvids))

archives={'X': 'Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_vibration_20261005_0950\\X\\local_recovery_v2', 'Y': 'Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_vibration_20261005_0950\\Y\\local_recovery', 'Z': 'Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_vibration_20261005_0950\\Z\\local_recovery'}
expected={'X': {4278: 6.142534402897581e-05, 4280: 3.897111128026154e-06, 4282: 2.8947886676178314e-05, 4285: 1015.0360717773438, 4286: 102.99742126464844, 4287: 512.7584838867188, 4288: 1443164288.0, 4289: 90324504.0, 4291: 0.002216146793216467, 4293: 0.0007716785185039043, 4295: 0.003044667188078165, 4327: 2.8059696433047066e-06, 4329: 149.8616180419922, 4331: 6.997177592893422e-07, 4333: 18.767192840576172, 4335: 2.33660339290509e-05, 4337: 512.7584838867188}, 'Y': {4297: 1.2149919257353758e-06, 4298: 87.87527465820312, 4299: 1.2274736945983022e-05, 4300: 224.2532501220703, 4301: 2.9746011932729743e-05, 4302: 309.7116394042969, 4303: 29287720.0, 4304: 17850004.0, 4306: 0.0002007094881264493, 4308: 0.0003535753348842263, 4310: 0.0003899412404280156, 4340: 3.3603637916712614e-07, 4342: 9.641519546508789, 4344: 9.514318435321911e-07, 4346: 164.11117553710938, 4348: 1.9450179024715908e-05, 4350: 309.7116394042969}, 'Z': {4312: 1.4838046809018124e-05, 4313: 490.64483642578125, 4314: 3.3203967177541927e-05, 4315: 357.3179931640625, 4316: 8.060016261879355e-05, 4317: 1516.6832275390625, 4318: 71386584.0, 4319: 32481930.0, 4321: 0.001116856699809432, 4323: 0.0009520176681689918, 4325: 0.0007208787719719112, 4353: 1.624388119125797e-06, 4355: 45.98423385620117, 4357: 2.3607053662999533e-06, 4359: 47.13393783569336, 4361: 5.2674102335004136e-05, 4363: 1516.6832275390625}}
hotspots=[('X', 'RMS equivalent stress - all bodies', 29373, 7017, 1443200000.0), ('X', 'RMS equivalent stress - PCB', 173651, 105927, 90325000.0), ('Y', 'RMS equivalent stress - all bodies', 95538, 47923, 29288000.0), ('Y', 'RMS equivalent stress - PCB', 208677, 110645, 17850000.0), ('Z', 'RMS equivalent stress - all bodies', 36190, 8273, 71387000.0), ('Z', 'RMS equivalent stress - PCB', 173648, 75325, 32482000.0)]

# Durable result references point to preserved archives outside generated folders.
for axis in ['X','Y']:
 a=rvs[['X','Y','Z'].index(axis)]
 path=System.IO.Path.Combine(archives[axis],'file.rst')
 assert System.IO.File.Exists(path)
 a.Solution.ReadGivenAnsysResultFileByReference(path,Ansys.Mechanical.DataModel.Enums.UnitSystemIDType.UnitsMKS)
 a.Solution.EvaluateAllResults()
for axis in ['X','Y','Z']:
 a=rvs[['X','Y','Z'].index(axis)]
 assert unicode(a.Solution.ObjectState)=='Solved'
 for oid,value in expected[axis].items():
  result=ExtAPI.DataModel.GetObjectById(oid)
  assert unicode(result.ObjectState)=='Solved'
  assert abs(result.Maximum.Value-value)<=max(abs(value)*1e-10,1e-15)
assert unicode(rvmodal.Solution.ObjectState)=='Solved'
md=ExtAPI.DataModel.MeshDataByName('Global')
remaining=set(h[3] for h in hotspots);body_map={}
for body in Model.Geometry.GetChildren(DataModelObjectCategory.Body,True):
 if not remaining:break
 geom=body.GetGeoBody().Id
 found=remaining.intersection(set(md.MeshRegionById(geom).ElementIds))
 for elem in found:body_map[elem]=(unicode(body.Name),geom)
 remaining.difference_update(found)
assert not remaining
rows=['case\tscope\tnode\telement\tstress_pa_rounded\tbody\tgeometry_id']
for axis,name,node,elem,value in hotspots:
 body,geom=body_map[elem]
 rows.append('\t'.join(map(unicode,[axis,name,node,elem,value,body,geom])))
System.IO.File.WriteAllText(System.IO.Path.Combine(RV_ROOT,'stress_hotspot_bodies.tsv'),'\n'.join(rows))
rows=['axis\tanalysis_id\tstate\tarchived_result']
for axis in ['X','Y','Z']:
 a=rvs[['X','Y','Z'].index(axis)]
 rows.append('\t'.join([axis,str(a.ObjectId),unicode(a.Solution.ObjectState),System.IO.Path.Combine(archives[axis],'file.rst')]))
System.IO.File.WriteAllText(System.IO.Path.Combine(RV_ROOT,'final_mechanical_state.tsv'),'\n'.join(rows))
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')
System.IO.File.WriteAllText(System.IO.Path.Combine(RV_ROOT,'ALL_CASES_VERIFIED.txt'),System.DateTime.UtcNow.ToString('o'))

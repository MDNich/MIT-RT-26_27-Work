from rv_paths import *
import csv,json,subprocess
archives={a:win(Path((R/a/'accepted_native_directory.txt').read_text())) for a in ['X','Y','Z']}
expected={a:{int(row['result_id']):float(row['maximum'].split()[0]) for row in csv.DictReader((R/a/'result_summary.tsv').open(),delimiter='\t')} for a in ['X','Y','Z']}
hotspots=[]
for a in ['X','Y','Z']:
 for name,x in json.loads((R/a/'stress_hotspots.json').read_text()).items():
  hotspots.append((a,name,x['node'],x['element'],x['value_pa']))
source='archives='+repr(archives)+'\nexpected='+repr(expected)+'\nhotspots='+repr(hotspots)+'\n'
source+=r'''
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
'''
z=subprocess.run(['python3','/tmp/pcb_request.py'],input=source,text=True,capture_output=True)
print(z.stdout,z.stderr);z.check_returncode()

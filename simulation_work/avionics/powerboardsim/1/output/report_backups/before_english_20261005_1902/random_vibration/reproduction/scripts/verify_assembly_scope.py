from rv_paths import *
import csv,json,collections,math
bodies=list(csv.DictReader((R/'assembly_body_inventory.tsv').open(),delimiter='\t'))
assert len(bodies)==208 and all(b['suppressed']=='False' and int(b['elements'])>0 for b in bodies)
bynode={};counts=collections.Counter()
for r in csv.DictReader((R/'assembly_body_nodes.tsv').open(),delimiter='\t'):
 n=int(r['node']);assert n not in bynode;bynode[n]=r['body_id'];counts[r['body_id']]+=1
assert len(bynode)==368754
bodymax={}
for axis,rid in [('X',4278),('Y',4301),('Z',4316)]:
 vals={};present=collections.Counter()
 with (R/axis/('result_'+str(rid)+'.txt')).open(encoding='cp1252') as f:
  next(f)
  for line in f:
   n,v=line.split();v=float(v.replace(',','.'));assert math.isfinite(v)
   bid=bynode[int(n)];present[bid]+=1;vals[bid]=max(vals.get(bid,0),v)
 assert present==counts and len(vals)==208
 bodymax[axis]=vals
out=[]
for b in bodies:
 row=dict(b)
 for axis in 'XYZ':row[axis+'_case_peak_component_rms_mm']=bodymax[axis][b['object_id']]*1000
 out.append(row)
with (R/'assembly_body_response_audit.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
audit={'meshed_unsuppressed_bodies':208,'ecad_component_bodies':sum(b['name'].startswith('COMP_') for b in bodies),'all_bodies_have_response_in_all_three_cases':True,'covered_nodes_per_case':368754,'solid_elements':sum(int(b['elements']) for b in bodies),'component_geometry_note':'Imported ECAD solids; this does not establish detailed package/solder-joint validation.'}
(R/'assembly_scope_audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit,indent=2))

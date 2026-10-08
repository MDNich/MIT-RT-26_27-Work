from pathlib import Path
import numpy as np,csv,json,sys,re
T=Path(__file__).resolve().parents[1];axis=sys.argv[1];O=T/('expand_'+axis);x=np.load(T/('transient_'+axis)/'modal_coordinates.npy');ph=list(csv.DictReader((T/'modal_validation_shapes.csv').open()));rs=list(csv.DictReader((O/'native_node_checks.csv').open()));aa=[];ex=[]
for r in rs:
 node=int(r['node']);t=float(r['time']);i=np.argmin(abs(x[:,0]-t));assert abs(x[i,0]-t)<1e-6
 mat=np.array([[float(p[z]) for z in ['ux','uy','uz']] for p in ph if int(p['node'])==node]);e=x[i,1:39]@mat;a=np.array([float(r[z]) for z in ['ux','uy','uz']]);aa.extend(a);ex.extend(e)
diff=np.linalg.norm(np.array(aa)-ex)/np.linalg.norm(ex);assert diff<1e-5
assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',(O/'solve.out').read_text())
times=np.loadtxt(O/'times.txt');assert len(times)==480;assert np.allclose(np.diff(times),1/16384,rtol=0,atol=1e-12)
a={'result_sets':480,'first_time_s':times[0],'last_time_s':times[-1],'sampled_sets':[1,2,120,240,360,480],'nodes_per_set':7,'relative_L2_error_U_vs_modal_sum':float(diff),'rst_sha256':(O/'rst.sha256').read_text(encoding='utf-16').strip(),'qualification':'native nodal expansion, no element stress results'}
(O/'ACCEPTED.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))

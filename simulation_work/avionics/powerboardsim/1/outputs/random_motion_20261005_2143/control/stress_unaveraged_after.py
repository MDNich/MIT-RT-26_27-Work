from pathlib import Path
import time,subprocess,json,numpy as np,csv
T=Path(__file__).resolve().parents[1]
while not (T/'dpf_stress_frames.json').exists():time.sleep(3)
with (T/'stress_prepass_unaveraged.log').open('w') as log:
 subprocess.run(['python3',str(T/'control/native_ironpython.py'),str(T/'control/stress_prepass_unaveraged.py')],stdout=log,stderr=log,check=True)
p=T/'dpf_stress_unaveraged_frames.json';rows=json.loads(p.read_text());assert len(rows)==480
q=np.load(T/'transient_X/modal_coordinates.npy',mmap_mode='r');sh=list(csv.DictReader((T/'modal_validation_shapes.csv').open()));srows=np.loadtxt(T/'dpf_global_stress_check/modal_nodes.csv',delimiter=',')
smats={n:np.zeros((38,6)) for n in [149869,173651]}
for k,n,c,v in srows:smats[n][int(k)-1,int(c)-1]=v
ua=[];ue=[];sa=[];se=[]
for i,r in enumerate(rows,1):
 assert r['frame']==i and abs(r['time_s']-(1+i/16384))<1e-12
 assert r['element_count']==39014 and r['maximum_Pa']>=r['minimum_Pa']>=0
 qq=q[np.argmin(abs(q[:,0]-r['time_s'])),1:39]
 for key,v in r['u_nodes'].items():
  mat=np.array([[float(t[c]) for c in ['ux','uy','uz']] for t in sh if int(t['node'])==int(key)]);ua.extend(v);ue.extend(qq@mat)
 for key,v in r['stress_nodes'].items():sa.extend(v);se.extend(qq@smats[int(key)])
uerr=float(np.linalg.norm(np.array(ua)-ue)/np.linalg.norm(ue));serr=float(np.linalg.norm(np.array(sa)-se)/np.linalg.norm(se));assert uerr<1e-5 and serr<1e-10
out={'frames':480,'element_count':39014,'relative_L2_U':uerr,'relative_L2_global_stress':serr,'maximum_dynamic_unaveraged_von_Mises_Pa':max(x['maximum_Pa'] for x in rows),'minimum_Pa':min(x['minimum_Pa'] for x in rows),'qualification':'Numerical fields accepted; native rendering and video checks remain required. Static mean stress excluded.'}
(T/'stress_video_fields_ACCEPTED.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))

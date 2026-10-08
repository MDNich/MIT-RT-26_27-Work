from pathlib import Path
import subprocess,time,json,ast,numpy as np
T=Path(__file__).resolve().parents[1]
while not (T/'stress_video_fields_ACCEPTED.json').exists():time.sleep(3)
with (T/'pilot_modal_dpf/probe.log').open('w') as f:
 subprocess.run(['python3',str(T/'control/native_ironpython.py'),str(T/'control/modal_dpf_probe.py')],stdout=f,stderr=f,check=True)
rows=json.loads((T/'pilot_modal_dpf/dpf_nodes.json').read_text());native=ast.literal_eval((T/'pilot_modal_dpf/native_audit.txt').read_text());a=[];e=[]
for r in rows:
 for n,v in r['nodes'].items():a.extend(v);e.extend(np.array(native['nodes'][int(n)])*r['phase_factor'])
err=np.linalg.norm(np.array(a)-e)/np.linalg.norm(e);assert err<1e-6
out={'frequency_Hz':native['frequency_Hz'],'normalized_maximum':native['maximum'],'relative_L2_phase_vectors':float(err),'phase_frames':[x['frame'] for x in rows],'visible_peak_m':.003,'native_graphics_pending':True}
(T/'pilot_modal_dpf/FIELDS_ACCEPTED.json').write_text(json.dumps(out,indent=2));print(out)

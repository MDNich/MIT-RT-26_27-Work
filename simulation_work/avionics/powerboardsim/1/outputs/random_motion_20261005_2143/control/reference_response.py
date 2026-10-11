from pathlib import Path
import numpy as np,json,csv
T=Path(__file__).resolve().parents[1];R=T.parents[1]/'outputs/random_vibration_20261005_0950';rows=list(csv.DictReader((T/'modal_validation_shapes.csv').open()));ns=sorted({int(x['node']) for x in rows});phi=np.zeros((38,len(ns),3));wn=np.zeros(38)
for x in rows:
 i=int(x['mode'])-1;j=ns.index(int(x['node']));wn[i]=2*np.pi*float(x['frequency_Hz']);phi[i,j]=[float(x[k]) for k in ['ux','uy','uz']]
expected=json.loads((T/'validation_nodes.json').read_text())['expected_rms'];output={}
for axis in 'XYZ':
 inp=np.load(T/'inputs'/(axis+'.npz'));a=inp['periodic_acceleration'];f=inp['frequency'];A=np.fft.rfft(a);w=2*np.pi*f;gamma=np.array([float(x['participation']) for x in csv.DictReader((R/'modal_basis'/('participation_'+axis+'.csv')).open())]);q=np.empty((len(a),38))
 for m in range(38):q[:,m]=np.fft.irfft(-gamma[m]*A/(wn[m]**2-w**2+2j*.02*wn[m]*w),n=len(a))
 np.save(T/('reference_q_'+axis+'.npy'),q)
 u=q@phi.reshape(38,-1);rms=np.sqrt(np.mean(u*u,axis=0)).reshape(len(ns),3)
 audit=[]
 for item in expected:
  if item['base']!=axis:continue
  value=float(rms[ns.index(item['node']),"XYZ".index(item['response'])]);audit.append(dict(item,reference_rms_m=value,relative_difference=value/item['rms_m']-1))
 output[axis]=audit;print(axis,audit,flush=True)
(T/'reference_response_audit.json').write_text(json.dumps(output,indent=2))

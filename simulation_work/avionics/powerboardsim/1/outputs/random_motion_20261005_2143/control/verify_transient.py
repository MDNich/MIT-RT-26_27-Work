from pathlib import Path
import sys,json,re,csv
import numpy as np
T=Path(__file__).resolve().parents[1];P=T.parents[1];R=P/'outputs/random_vibration_20261005_0950';name=sys.argv[1];O=T/name;m=json.loads((O/'manifest.json').read_text());axis=m['axis'];dt=1/m['fs_Hz'];duration=m['duration_s']
s=(O/'solve.out').read_text();assert 'RUN COMPLETED' in s;assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',s)
lines=(O/'file.mcf').read_text().splitlines();valid=[]
for line in lines:
 cells=line.split()
 if len(cells)>=39:
  try:row=[float(v.replace('D','E')) for v in cells]
  except ValueError:continue
  valid.append(row)
x=np.array(valid);assert x.ndim==2 and len(x)>10 and x.shape[1]>=39,x.shape
np.save(O/'modal_coordinates.npy',x);times=x[:,0];assert np.all(np.diff(times)>0);assert abs(times[-1]-duration)<dt*.01
assert np.isfinite(x).all();nstep=round(duration/dt);q=np.zeros((nstep+1,38));u=np.zeros(38);v=np.zeros(38);acc=np.zeros(38)
phirows=list(csv.DictReader((T/'modal_validation_shapes.csv').open()));wn=np.array([float(next(r for r in phirows if int(r['mode'])==i)['frequency_Hz'])*2*np.pi for i in range(1,39)]);gam=np.array([float(r['participation']) for r in csv.DictReader((R/'modal_basis'/('participation_'+axis+'.csv')).open())]);z=2*.02*wn;k=wn**2
inputdata=np.load(T/'inputs'/(axis+'.npz'));force_input=np.interp(np.arange(nstep+1)*dt,inputdata['t'],inputdata['acceleration']);den=1+.5*dt*z+.25*dt*dt*k
for i in range(1,nstep+1):
 anew=(-gam*force_input[i]-z*(v+.5*dt*acc)-k*(u+dt*v+.25*dt*dt*acc))/den
 u=u+dt*v+.25*dt*dt*(acc+anew);v=v+.5*dt*(acc+anew);acc=anew;q[i]=u
expected=q[np.rint(times/dt).astype(int)];actual=x[:,1:39];relerr=float(np.linalg.norm(actual-expected)/np.linalg.norm(expected));maxerr=float(abs(actual-expected).max());assert relerr<.005,(relerr,maxerr)
ns=sorted({int(r['node']) for r in phirows});phi=np.zeros((38,len(ns),3))
for r in phirows:phi[int(r['mode'])-1,ns.index(int(r['node']))]=[float(r[c]) for c in ['ux','uy','uz']]
response=actual@phi.reshape(38,-1);stationary=times>=1 if duration>=2 else times>=.125;rms=np.sqrt(np.mean(response[stationary]**2,axis=0)).reshape(len(ns),3)
comparisons=[]
for r in json.loads((T/'validation_nodes.json').read_text())['expected_rms']:
 if r['base']!=axis:continue
 value=float(rms[ns.index(r['node']),"XYZ".index(r['response'])]);comparisons.append(dict(r,transient_rms_m=value,relative_difference=value/r['rms_m']-1))
audit={'axis':axis,'errors':0,'native_samples':len(x),'duration_s':float(times[-1]),'fs_Hz':m['fs_Hz'],'independent_newmark_relative_l2_error':relerr,'maximum_modal_coordinate_error':maxerr,'rms_comparisons':comparisons,'relative_support_max_m':float(abs(response[:,ns.index(136765)*3:ns.index(136765)*3+3]).max())}
assert audit['relative_support_max_m']<1e-12
if duration>=9:assert max(abs(r['relative_difference']) for r in comparisons)<.02, comparisons
(O/'ACCEPTED.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit,indent=2))

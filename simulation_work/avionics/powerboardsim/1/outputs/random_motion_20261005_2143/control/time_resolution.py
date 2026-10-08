from pathlib import Path
import numpy as np,json,csv
T=Path('/Users/mdn/Developer/MIT_Rkt_Team/2026-7/MIT-RT-26_27-Work/simulation_work/avionics/powerboardsim/1/outputs/random_motion_20261005_2143');R=T.parents[1]/'outputs/random_vibration_20261005_0950'
rows=list(csv.DictReader((T/'modal_validation_shapes.csv').open()));nodes=sorted({int(r['node']) for r in rows});phi=np.zeros((38,len(nodes),3));wn=np.zeros(38)
for r in rows:
 j=int(r['mode'])-1;wn[j]=2*np.pi*float(r['frequency_Hz']);phi[j,nodes.index(int(r['node']))]=[float(r[c]) for c in ['ux','uy','uz']]
expected=json.loads((T/'validation_nodes.json').read_text())['expected_rms'];result={}
for axis in 'XYZ':
 z=np.load(T/'inputs'/(axis+'.npz'));f=z['frequency'];mask=(f>=20)&(f<=2000);w=2*np.pi*f[mask];A=np.fft.rfft(z['periodic_acceleration'])[mask];N=len(z['periodic_acceleration']);gam=np.array([float(r['participation']) for r in csv.DictReader((R/'modal_basis'/('participation_'+axis+'.csv')).open())]);result[axis]=[]
 for fs in [32768,65536,131072]:
  wd=2*fs*np.tan(w/(2*fs));H=-gam[None,:]/(wn[None,:]**2-wd[:,None]**2+2j*.02*wn[None,:]*wd[:,None]);Q=A[:,None]*H
  for e in expected:
   if e['base']!=axis:continue
   U=Q@phi[:,nodes.index(e['node']),'XYZ'.index(e['response'])];rms=float(np.sqrt(2*np.sum(abs(U)**2))/N)
   result[axis].append(dict(e,fs_Hz=fs,discrete_newmark_stationary_rms_m=rms,relative_difference=rms/e['rms_m']-1))
(T/'time_resolution_audit.json').write_text(json.dumps(result,indent=2));print({fs:max(abs(r['relative_difference']) for a in result.values() for r in a if r['fs_Hz']==fs) for fs in [32768,65536,131072]})

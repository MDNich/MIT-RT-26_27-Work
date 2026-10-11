"""Compare audited attachment curves on an overlapping displacement interval."""
from pathlib import Path
import json,sys,hashlib
import numpy as np
S=Path(__file__).resolve().parent.parent
reference,trial=sys.argv[1:3]

def read(case):
 d=S/'runtime'/case
 a=d/'ACCEPTED.json'
 if not a.exists():a=d/'CONVERGED_STATES_AUDIT.json'
 audit=json.loads(a.read_text()); assert (d/'LOAD_HISTORY_VERIFIED.json').exists()
 h=np.atleast_1d(np.genfromtxt(d/'history.csv',delimiter=',',names=True))
 return d,h,audit
rd,r,ra=read(reference);td,t,ta=read(trial)
xr=abs(r['ux_mm']);xt=abs(t['ux_mm'])
lo=max(xr.min(),xt.min());hi=min(xr.max(),xt.max());mask=(xr>=lo-1e-9)&(xr<=hi+1e-9)
x=xr[mask];assert len(x)>5
result=dict(reference=reference,trial=trial,overlap_displacement_mm=[float(lo),float(hi)],points=len(x),method='Trial linearly interpolated only inside overlap onto reference saved states; no extrapolation. Magnitudes permit +/-X comparison.',hashes={reference:hashlib.sha256((rd/'history.csv').read_bytes()).hexdigest(),trial:hashlib.sha256((td/'history.csv').read_bytes()).hexdigest()})
for k in ['fx_N','clamp1_N','clamp2_N','peeq']:
 vr=abs(r[k][mask]); vt=np.interp(x,xt,abs(t[k]));delta=abs(vt-vr)
 result[k]={'max_abs_difference':float(delta.max()),'max_relative_difference':float((delta/np.maximum(vr,1)).max()),'rms_difference':float(np.sqrt(np.mean(delta**2)))}
dr=np.maximum.reduce([r[k] for k in ['dtop','dmid','dbot']])[mask]
dt=np.maximum.reduce([t[k] for k in ['dtop','dmid','dbot']])
result['damage_max_abs_difference']=float(np.max(abs(np.interp(x,xt,dt)-dr)))
result['damage_onset_reference']=ra['first_damage'];result['damage_onset_trial']=ta['first_damage']
if ra['first_damage'] and ta['first_damage']:
 result['onset_displacement_difference_mm']=abs(abs(ra['first_damage']['ux_mm'])-abs(ta['first_damage']['ux_mm']))
trial_source=json.loads((td/'config.json').read_text())['case']
result['trial_source_case']=trial_source
result['trial_is_snapshot']=(td/'SNAPSHOT_INTENT.json').exists()
if reference=='cont_nominal' and trial_source=='cont_force5em5':
 thresholds=json.loads((S/'audit/force_tolerance_comparison_plan.json').read_text())['screening_thresholds']
 checks={'force':result['fx_N']['max_relative_difference']<=thresholds['force_relative_fraction'],
 'clamps':max(result[k]['max_relative_difference'] for k in ['clamp1_N','clamp2_N'])<=thresholds['clamp_relative_fraction'],
 'damage':result['damage_max_abs_difference']<=thresholds['damage_absolute'],
 'onset':result.get('onset_displacement_difference_mm',1e9)<=thresholds['onset_displacement_difference_mm']}
 result.update(screening_thresholds=thresholds,screening_checks=checks,screening_passed=all(checks.values()))
out=S/'results'/f'{reference}_vs_{trial}.json';out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

"""Audit a failed coupon's converged-only export; never mark its solve complete."""
from pathlib import Path
import numpy as np,json,sys
S=Path(__file__).resolve().parent.parent
D=S/'runtime'/sys.argv[1]
h=np.atleast_1d(np.genfromtxt(D/'accepted_history.csv',names=True,delimiter=','))
assert np.all(np.diff(h['time'])>0)
assert np.all(np.diff(h['damage'])>=-1e-5)
expected=np.log1p(h['ux_mm'])-h['sx_MPa']/np.maximum(1-h['damage'],1e-4)/205000
res=float(np.max(abs(expected-h['eppl'])))
assert res<1e-4
sel=(h['damage']>.02)&(h['damage']<.9)
slope,intercept=np.polyfit(h['eppl'][sel],h['damage'][sel],1)
onset=float(-intercept/slope)
assert abs(onset-.3)<.015
imax=int(np.argmax(h['fx_N']))
res=dict(case=D.name,scope='Converged states only; full coupon solution failed',rows=len(h),onset_from_fit=onset,max_log_strain_residual=res,last_displacement_mm=float(h['ux_mm'][-1]),last_peeq=float(h['eppl'][-1]),last_damage=float(h['damage'][-1]),peak_force_N=float(h['fx_N'][imax]),peak_displacement_mm=float(h['ux_mm'][imax]))
(D/'CONVERGED_STATES_AUDIT.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))

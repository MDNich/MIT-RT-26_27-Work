"""Validate collected native output and summarize accepted recorded load states."""
from pathlib import Path
import json,re,sys,hashlib
import numpy as np
S=Path(__file__).resolve().parent.parent
case=sys.argv[1];D=S/'runtime'/case
partial='--partial' in sys.argv
cfg=json.loads((D/'config.json').read_text())
out=(D/'run.out').read_text(errors='replace')
h=np.atleast_1d(np.genfromtxt(D/'history.csv',delimiter=',',names=True))
def event(mask):
    ids=np.where(mask)[0]
    if not len(ids):return None
    i=int(ids[0])
    return dict(row=i,ux_mm=float(h['ux_mm'][i]),force_N=float(abs(h['fx_N'][i])))
d=dict(case=case,input_sha256=json.loads((D/'input_sha256.json').read_text()),
       native_errors=re.findall(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)',out),
       native_warnings=re.findall(r'NUMBER OF WARNING\s+MESSAGES ENCOUNTERED=\s*(\d+)',out),
       completed_native_footer='MAPDL RUN COMPLETED' in out or 'Elapsed Time (sec)' in out)
if cfg.get('model')=='one uniform uniaxial shell':
    expected=np.log1p(h['ux_mm'])-h['sx_MPa']/np.maximum(1-h['damage'],1e-4)/205000
    active=(h['damage']>.02)&(h['damage']<.95)
    if np.count_nonzero(active)>2:
        slope,intercept=np.polyfit(h['eppl'][active],h['damage'][active],1)
        d.update(estimated_onset=-float(intercept/slope),inferred_characteristic_length_mm=float(slope*.12))
    d.update(rows=len(h),final_time=float(h['time'][-1]),max_damage=float(max(h['damage'])),
             max_log_plastic_strain_residual=float(max(abs(h['eppl']-expected))),
             first_damage=event(h['damage']>1e-4),max_force_N=float(max(abs(h['fx_N']))))
    assert len(h)>20 and np.all(np.diff(h['time'])>0)
    assert d['final_time']>=.99999 and d['max_damage']>.99
    assert abs(d['estimated_onset']-.3)<.015,d
    assert d['max_log_plastic_strain_residual']<.03,d
    assert np.all(np.diff(h['damage'])>=-1e-5)
else:
    b=np.atleast_1d(np.genfromtxt(D/'balance.csv',delimiter=',',names=True))
    damage=np.maximum.reduce([h['dtop'],h['dmid'],h['dbot']])
    index=int(np.argmax(abs(h['fx_N'])))
    d.update(rows=len(h),final_time=float(h['time'][-1]),final_ux_mm=float(h['ux_mm'][-1]),
             peak_force_N=float(abs(h['fx_N'][index])),peak_ux_mm=float(h['ux_mm'][index]),
             peak_row=index,final_force_N=float(abs(h['fx_N'][-1])),max_damage=float(max(damage)),
             final_peeq=float(h['peeq'][-1]),first_damage=event(damage>1e-4),
             first_damage_95=event(damage>=.95),first_damage_99=event(damage>=.99),
             max_lateral_balance_N=float(max(abs(b['rx_N']))),
             max_y_balance_N=float(max(abs(b['ry_N']))),
             max_z_balance_N=float(max(abs(b['rz_N']))),
             max_lateral_relative_balance=float(max(abs(b['rx_N'])/np.maximum(abs(h['fx_N']),1))),
             target_reached=abs(abs(h['ux_mm'][-1])-cfg['displacement_mm'])<1e-6,
             strain_limit_stop=(D/'STOP_STRAIN_LIMIT.txt').exists(),
             interpretation='Maximum element-summary damage; no geometric crack or element deletion.')
    assert len(h)==len(b) and np.all(np.diff(h['time'])>0)
    assert np.all(damage>=-1e-8) and np.all(damage<=1+1e-6)
    assert np.all(np.diff(damage)>=-1e-4),'Nonmonotonic global damage maximum'
    assert d['max_lateral_relative_balance']<.001
    assert d['max_y_balance_N']<.01 and d['max_z_balance_N']<.1
    for row in h:
        j=int(row['step'])
        a=np.atleast_1d(np.genfromtxt(D/f'damage_{j}.csv',delimiter=',',names=True))
        n=np.atleast_1d(np.genfromtxt(D/f'nodes_{j}.csv',delimiter=',',names=True))
        assert len(a)==cfg['shell_elements']
        assert len(n)==json.loads((D/'mesh.json').read_text())['pilot']-1
        assert np.all(np.isfinite(np.asarray(a.tolist(),dtype=float)))
for f in h.dtype.names:assert np.all(np.isfinite(h[f])),f
assert d['native_errors'],d
if not partial:
    assert int(d['native_errors'][-1])==0,d
else:
    assert cfg.get('model')!='one uniform uniaxial shell','Use converged-only coupon diagnostic.'
    assert (D/'last_good.db').exists()
    # Each attachment row is emitted only after the native CNVG=1 gate.
    d['qualification']='Validated recorded converged states only; native errors retained. No successful full-horizon claim.'
assert d['completed_native_footer'],d
(D/('CONVERGED_STATES_AUDIT.json' if partial else 'ACCEPTED.json')).write_text(json.dumps(d,indent=2))
(S/'results'/f'{case}_summary.json').write_text(json.dumps(d,indent=2))
print(json.dumps({k:v for k,v in d.items() if k!='input_sha256'},indent=2))

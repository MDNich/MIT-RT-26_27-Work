from pathlib import Path
import sys,re,json,numpy as np,hashlib
D=Path(sys.argv[1]).resolve();case=D.name;cfg=json.loads((D/'config.json').read_text())
s=(D/'run.out').read_text(errors='replace')
errs=int(re.findall(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)',s)[-1]);warns=int(re.findall(r'NUMBER OF WARNING\s+MESSAGES ENCOUNTERED=\s*(\d+)',s)[-1])
h=np.genfromtxt(D/'history.csv',delimiter=',',names=True);b=np.genfromtxt(D/'balance.csv',delimiter=',',names=True)
assert errs==0,errs
assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',(D/'post_corrected.out').read_text(errors='replace')),'Read-only postprocessor did not complete successfully'
assert len(h)>1 and np.all(np.isfinite(h.view(float)))
expected=cfg.get('end_time',2 if 'mu' in cfg else 1)
assert abs(h['time'][-1]-expected)<1e-8 and abs(h['ux_mm'][-1]-cfg['sign']*cfg['displacement_mm'])<1e-8
assert np.all(np.diff(h['time'])>0)
for f in ['nodal.csv','element_top.csv','element_bottom.csv']:
 a=np.genfromtxt(D/f,delimiter=',',names=True);assert np.all(np.isfinite(a.view(float)))
 assert len(a)==(cfg['shell_elements'] if 'element' in f else json.loads((D/'mesh.json').read_text())['pilot']-1),(f,len(a))
rel=np.max(np.abs(b['force_x_N'])/np.maximum(np.abs(h['fx_N']),1))
maxy=float(np.max(np.abs(b['force_y_N'])));maxz=float(np.max(np.abs(b['force_z_N'])))
audit=dict(case=case,errors=errs,warnings=warns,last_time=float(h['time'][-1]),last_displacement_mm=float(h['ux_mm'][-1]),last_force_N=float(h['fx_N'][-1]),max_plastic_strain=float(h['max_eppl'][-1]),max_lateral_force_balance_N=float(np.max(np.abs(b['force_x_N']))),max_lateral_force_balance_normalized=float(rel),max_transverse_balance_N=maxy,max_normal_balance_N=maxz,run_sha256=hashlib.sha256((D/'run.dat').read_bytes()).hexdigest())
# Predefined practical equilibrium audit, in addition to native nonlinear convergence.
assert rel<.01 and maxy<.1 and maxz<.2,audit
if 'mu' in cfg:
 ch=np.genfromtxt(D/'contact_history.csv',delimiter=',',names=True)
 mask=ch['time']>cfg.get('pull_start_time',1)
 assert max(np.ptp(ch[n][mask]) for n in ['washer1_uz','washer2_uz'])<1e-8,'Preload displacement not constant during pull'
 if cfg.get('pull_start_time')==2:
  locked=ch[np.isclose(ch['time'],2)]
  assert len(locked)==1
  assert all(abs(float(locked[n][0])-750)<.2 for n in ['washer1_RFz','washer2_RFz']),'Preload transfer not retained'
 audit.update(max_sliding_mm=float(np.max(ch['max_slide'])),peak_pressure_MPa=float(np.max(ch['max_pressure'])),final_washer_reactions_N=[float(ch[n][-1]) for n in ['washer1_RFz','washer2_RFz']])
if (D/'moment_balance.csv').exists():
 mm=np.genfromtxt(D/'moment_balance.csv',delimiter=',',names=True)
 assert np.all(np.isfinite(mm.view(float)))
 audit['max_moment_imbalance_Nmm']={k:float(np.max(np.abs(mm[k]))) for k in ['mx_Nmm','my_Nmm','mz_Nmm']}
 ms=json.loads((D/'mesh.json').read_text());r0=np.array(ms['nodes'][str(ms['pilot'])])
 rr=r0+np.column_stack([h['ux_mm'],h['uy_mm'],h['uz_mm']]);ff=np.column_stack([b['force_x_N'],b['force_y_N'],b['force_z_N']]);mom=np.column_stack([mm['mx_Nmm'],mm['my_Nmm'],mm['mz_Nmm']])
 mc=mom-np.cross(rr,ff)
 audit['max_moment_imbalance_at_battery_centre_Nmm']={k:float(v) for k,v in zip(['x','y','z'],np.max(np.abs(mc),axis=0))}
 np.savetxt(D/'moment_balance_battery_centre.csv',np.column_stack([h['time'],mc]),delimiter=',',header='time,mx_Nmm,my_Nmm,mz_Nmm',comments='')

assert audit['max_plastic_strain']>=0
(D/'ACCEPTED.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit,indent=2))

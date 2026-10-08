from pull_paths import *
import json,numpy as np,csv
rows=[]
for D in (S/'runtime').iterdir():
 if not (D/'ACCEPTED.json').exists():continue
 a=json.loads((D/'ACCEPTED.json').read_text());cfg=json.loads((D/'config.json').read_text());h=np.genfromtxt(D/'history.csv',delimiter=',',names=True)
 mask=h['time']>cfg.get('pull_start_time',1) if 'mu' in cfg else h['time']>0
 hp=h[mask];u=np.abs(hp['ux_mm']);f=np.abs(hp['fx_N']);e=hp['max_eppl'];ix=np.where(e>1e-6)[0]
 peak_ix=np.argmax(f)
 row=dict(case=D.name,mesh_elements=cfg['shell_elements'],yield_MPa=cfg['yield_MPa'],tangent_MPa=cfg['tangent_MPa'],mu=cfg.get('mu','perfect grip'),direction=cfg['sign'],u_end_mm=u[-1],force_end_N=f[-1],max_force_in_run_N=f[peak_ix],max_force_displacement_mm=u[peak_ix],eppl_end_pct=e[-1]*100,rotation_y_end_deg=hp['roty'][-1]*180/np.pi,yield_first_detected_force_N=f[ix[0]] if len(ix) else None,yield_last_elastic_force_N=f[ix[0]-1] if len(ix) and ix[0]>0 else None,force_at_0p1mm_N=float(np.interp(.1,u,f)),force_at_0p25mm_N=float(np.interp(.25,u,f)))
 rows.append(row)
 out=np.column_stack([np.r_[0,u],np.r_[0,f],np.r_[0,e*100]])
 np.savetxt(S/'results'/f'{D.name}_curve.csv',out,delimiter=',',header='displacement_mm,force_N,plastic_pct',comments='')
 if 'mu' in cfg:
  ch=np.genfromtxt(D/'contact_history.csv',delimiter=',',names=True)
  row['max_slide_mm']=float(max(ch['max_slide']));row['end_preload_N']=[float(ch[x][-1]) for x in ['washer1_RFz','washer2_RFz']]
(S/'results/summary.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows,indent=2))

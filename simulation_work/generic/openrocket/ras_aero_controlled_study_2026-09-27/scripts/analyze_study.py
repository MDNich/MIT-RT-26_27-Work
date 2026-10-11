from pathlib import Path
import csv,json,math,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASES=['B01-smooth-square','B02-rough-square','B03-smooth-bevel','B04-slender-square','B05-slender-bevel']
MOTORS=['I500T-14A','J570W']
def read(path):
 rows=list(csv.DictReader(path.open()));assert rows and all(None not in r for r in rows)
 return {k:np.array([float(r[k]) for r in rows]) for k in rows[0] if k!='Stage'}
def stats(a,ras=False):
 t=a['Time (sec)' if ras else 'Time'];h=a['Altitude (ft)' if ras else 'Altitude']*(.3048 if ras else 1);v=a['Velocity (ft/sec)' if ras else 'Total velocity']*(.3048 if ras else 1)
 ma=a['Mach Number' if ras else 'Mach number'];ac=a['Accel (ft/sec^2)' if ras else 'Total acceleration']*(.3048 if ras else 1);apo=int(np.nanargmax(h));asc=t<=t[apo]
 return dict(apogee_m=float(h[apo]),time_to_apogee_s=float(t[apo]),vmax_m_s=float(np.nanmax(v[asc])),mach_max=float(np.nanmax(ma[asc])),accel_max_m_s2=float(np.nanmax(ac[asc])))
summary=[]
for base in BASES:
 for motor in MOTORS:
  name=base+'-'+motor;o=read(ROOT/'openrocket'/(name+'.csv'));f=read(ROOT/'openrocket'/(name+'-actual-h00125.csv'));r=read(ROOT/'rasaero'/(base+'-turbulent-'+motor+'.csv'));d=read(ROOT/'rasaero'/(name+'.csv'))
  so,sr,sf,sd=stats(o),stats(r,True),stats(f),stats(d,True)
  tr=r['Time (sec)'];to=o['Time'];burn=r['Thrust (lb)']>0
  thrustR=r['Thrust (lb)']*4.4482216152605;thrustO=np.interp(tr,to,o['Thrust']);massR=r['Weight (lb)']*.45359237;massO=np.interp(tr,to,o['Mass'])
  ascent=(tr<=sr['time_to_apogee_s'])&(tr>.01)
  diag=dict(launch_mass_error_g=float((massR[0]-o['Mass'][0])*1000),launch_cg_error_mm=float((r['CG (in)'][0]*.0254-o['CG location'][0])*1000),thrust_rmse_N=float(np.sqrt(np.mean((thrustR[burn]-thrustO[burn])**2))),thrust_max_difference_N=float(np.max(abs(thrustR[burn]-thrustO[burn]))),mass_max_difference_g=float(np.max(abs(massR[ascent]-massO[ascent]))*1000),actual_halfstep_apogee_delta_pct=100*(sf['apogee_m']/so['apogee_m']-1),flow_switch_apogee_pct=100*(sr['apogee_m']/sd['apogee_m']-1),max_ascent_ras_aoa_deg=float(np.max(abs(r['Angle of Attack (deg)'][ascent]))))
  statepath=ROOT/'evidence'/(base+'-turbulent-'+motor+'-same-state.csv')
  if statepath.exists():
   s=read(statepath);peak=int(np.argmax(s['velocity_m_s']));diag.update({f'same_state_peak_{key}':float(s[key][peak]) for key in ['ras_cd','or_cd','or_friction_cd','or_pressure_cd','or_base_cd']})
   area=math.pi*((2.26 if base.startswith(('B04','B05')) else 4)*.0254)**2/4
   rho=2*s['ras_drag_N']/(s['ras_cd']*area*s['velocity_m_s']**2);diag['density_ratio_median']=float(np.median(rho/s['or_density']))
   coast=(s['ras_thrust_N']==0)&(s['velocity_m_s']>30)&(abs(s['ras_aoa_deg'])<.01)
   g=-s['ras_vertical_accel']-s['ras_drag_N']/s['ras_mass_kg'];diag['ras_inferred_g_median']=float(np.median(g[coast])) if np.any(coast) else None
  replay_path=ROOT/'openrocket'/(name+'-ras-cd-replay.csv')
  if replay_path.exists():
   replay=stats(read(replay_path));diag['cd_replay_apogee_m']=replay['apogee_m'];diag['cd_replay_residual_pct']=100*(replay['apogee_m']/sr['apogee_m']-1)
  summary.append(dict(design=base,motor=motor,openrocket=so,rasaero=sr,rasaero_export_defaults=sd,delta_pct={k:100*(sr[k]/so[k]-1) for k in so},diagnostics=diag))
(ROOT/'comparison-results.json').write_text(json.dumps(summary,indent=2)+'\n')
for s in summary:
 print(s['design'],s['motor'],'OR',round(s['openrocket']['apogee_m'],2),'RAS',round(s['rasaero']['apogee_m'],2),'diff%',round(s['delta_pct']['apogee_m'],2),'V',round(s['rasaero']['vmax_m_s'],2),'M',round(s['rasaero']['mach_max'],3),'diag',s['diagnostics'])

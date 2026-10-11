from pull_paths import *
import numpy as np,json
A=S/'runtime/grip_lagrange';B=S/'runtime/grip_fine_lagrange'
if all((d/'ACCEPTED.json').exists() for d in [A,B]):
 a=np.genfromtxt(A/'history.csv',delimiter=',',names=True);b=np.genfromtxt(B/'history.csv',delimiter=',',names=True)
 uu=np.linspace(.025,.5,20);fa=np.interp(uu,a['ux_mm'],a['fx_N']);fb=np.interp(uu,b['ux_mm'],b['fx_N'])
 d=dict(coarse_elements=2304,fine_elements=9216,max_curve_relative_difference=float(max(abs((fa-fb)/fb))),force_endpoint_change_pct=float(100*(a['fx_N'][-1]/b['fx_N'][-1]-1)),plastic_increase_coarse_to_fine_pct=float(100*(b['max_eppl'][-1]/a['max_eppl'][-1]-1)),fine_force_N=float(b['fx_N'][-1]),fine_plastic_strain=float(b['max_eppl'][-1]))
 (S/'results/mesh_comparison.json').write_text(json.dumps(d,indent=2));print(d)

A=S/'runtime/friction_locked';B=S/'runtime/friction_locked_fine'
if all((d/'ACCEPTED.json').exists() for d in [A,B]):
 a=np.genfromtxt(A/'history.csv',delimiter=',',names=True);b=np.genfromtxt(B/'history.csv',delimiter=',',names=True)
 a=a[a['time']>2];b=b[b['time']>2]
 uu=np.linspace(.025,.5,20);fa=np.interp(uu,a['ux_mm'],a['fx_N']);fb=np.interp(uu,b['ux_mm'],b['fx_N'])
 d=dict(coarse_elements=2304,fine_elements=9216,max_curve_relative_difference=float(max(abs((fa-fb)/fb))),force_endpoint_change_pct=float(100*(a['fx_N'][-1]/b['fx_N'][-1]-1)),plastic_increase_coarse_to_fine_pct=float(100*(b['max_eppl'][-1]/a['max_eppl'][-1]-1)),fine_force_N=float(b['fx_N'][-1]),fine_plastic_strain=float(b['max_eppl'][-1]))
 (S/'results/contact_mesh_comparison.json').write_text(json.dumps(d,indent=2));print(d)

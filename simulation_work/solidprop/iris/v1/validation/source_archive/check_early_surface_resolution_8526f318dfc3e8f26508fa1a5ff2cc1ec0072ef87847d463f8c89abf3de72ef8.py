"""Independent early-heating diagnostic; no native files or queue are changed."""
import sys,json,hashlib,copy,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'model'))
from ops import atomic,disks,host_check,utc
from radial_model import RadialModel
base_path=ROOT/'ansystmp/runs/sustainer_al_pulse7_midpoint_joint320_geom005_smp10/config.json'
base=json.loads(base_path.read_text())
sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [base_path,ROOT/'model/radial_model.py',ROOT/'model/coupler.py',Path(__file__)]}
plan=[('n160_native_dt',160,.003125),('n160_tight_dt',160,.0001953125),('n320_native_dt',320,.0015625),('n320_tight_dt',320,.0001953125),('n640_tight_dt',640,.0001953125),('n1280_tight_dt',1280,.000048828125)]
out=ROOT/'ansystmp/heartbeat_checks/early_surface_resolution_20261106.json'
results=[]
for tag,rows,dt in plan:
 disks();cfg=copy.deepcopy(base);cfg['geometry']['phenolic_radial_rows']=rows;cfg['geometry']['aluminium_radial_rows']=rows//4;cfg['expected_elements']=(rows+rows//4)*cfg['geometry']['faces_per_row'];cfg['macro_dt_s']=dt
 m=RadialModel(cfg);start=time.monotonic();state,history,snaps=m.run(2.,dt=dt,record_dt=.003125,targets=[1.24375,1.5,2.],check=host_check,stop_at_property_limit=True)
 assert abs(state.time-2)<1e-8 and state.layer==0 and m.property_bracket is None
 assert m.max_energy_error<1e-6 and m.max_mass_error<1e-8
 samples=[]
 for t,s in snaps.items():
  h,Tg,flux,qhot,qouter=m.boundary(s,dt);rc=cfg['material']['char_reference_density_kg_m3'];a=float((s.alpha[0]*m.w[0]).sum()/m.vol[0]);available=max(rc*m.vol[0]*a-s.consumed[0],0.)
  samples.append(dict(time_s=t,hot_C=float(s.T[0]),layer=s.layer,surface_row_conversion=a,consumed_char_per_rad_m=float(s.consumed[0]),available_char_per_rad_m=float(available),prospective_next_step_applied_flux_kg_m2_s=flux,prospective_next_step_h_W_m2_K=h))
 results.append(dict(tag=tag,phenolic_rows=rows,casing_rows=rows//4,dt_s=dt,steps=m.steps,elapsed_s=time.monotonic()-start,max_energy_error=m.max_energy_error,max_mass_error=m.max_mass_error,configuration=cfg,samples=samples,history=history))
 atomic(out,dict(checked_utc=utc(),complete=len(results)==len(plan),independent_only=True,source_hashes=sources,plan=plan,results=results,qualification='Short independent reduced-model diagnostics of the first two seconds only. No layer removal or material-scope crossing occurred. Neither ANSYS output nor a burnthrough/lifetime estimate; no queued/native input was changed.'))
 print(tag,[(x['time_s'],x['hot_C']) for x in samples],m.steps,m.max_energy_error,flush=True)

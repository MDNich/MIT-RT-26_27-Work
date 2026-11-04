"""Check late booster heat-soak peaks before selecting native cooling horizons."""
import hashlib
import json
from radial_model import RadialModel
from ops import ROOT,TMP,atomic,disks,host_check


def main():
    disks();source=(ROOT/'model/radial_model.py').read_bytes();sha=hashlib.sha256(source).hexdigest()
    archive=ROOT/'validation/source_archive';archive.mkdir(exist_ok=True)
    (archive/f'radial_model_{sha}.py').write_bytes(source)
    for case in ['booster_al','booster_cf']:
        for tag,nph,ncase,dt,post in [('native_schedule',80,20,.0125,.25),('joint320',320,80,.0015625,.03125)]:
            p=ROOT/'validation/radial'/f'{case}_pulse7_cooling300_{tag}.json'
            if p.exists():continue
            cfg=json.loads((TMP/'runs'/f'{case}_pulse7_n80_dt0125'/'config.json').read_text())
            cfg['geometry'].update(phenolic_radial_rows=nph,aluminium_radial_rows=ncase)
            cfg.update(end_time_s=300,macro_dt_s=dt,post_pulse_macro_dt_s=post)
            m=RadialModel(cfg)
            s,h,ss=m.run(300,dt=dt,post_dt=post,record_dt=.25,
                targets=[.1,1,2,5,7,10,20,30,60,90,127,150,200,250,300],check=host_check,stop_at_property_limit=True)
            peaks={k:max(h,key=lambda a:a[k]) for k in ['interface_C','outer_C']}
            out=dict(method='Independent radial finite elements, NOT native ANSYS',configuration=cfg,model_sha256=sha,
                eligible_for_motor_lifetime=False,qualification='Exploratory prescribed pulse/cooling; sampled temperature peaks are not structural limits',
                final=h[-1],history=h,event_bracket_s=m.event_bracket,property_limit_bracket_s=m.property_bracket,
                sampled_peaks={k:dict(temperature_C=v[k],time_s=v['time_s']) for k,v in peaks.items()},
                max_energy_relative_error=m.max_energy_error,max_mass_relative_error=m.max_mass_error,
                profiles={str(t):dict(radius_m=m.r.tolist(),temperature_C=a.T.tolist(),mean_conversion=a.alpha.mean(axis=1).tolist(),removed_rows=a.layer) for t,a in ss.items()})
            atomic(p,out);print(json.dumps(dict(case=case,level=tag,final=out['final'],peaks=out['sampled_peaks'])),flush=True)


if __name__=='__main__':main()

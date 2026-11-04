"""Independent resolution checks for the native seven-second pulse schedule."""
import hashlib
import json
from radial_model import RadialModel
from ops import ROOT,TMP,atomic,host_check,disks

MODEL_BYTES=(ROOT/'model/radial_model.py').read_bytes()
MODEL_SHA=hashlib.sha256(MODEL_BYTES).hexdigest()
LEVELS=[('native_schedule',80,20,.0125,.25),('half_time',80,20,.00625,.125),
        ('quarter_time',80,20,.003125,.0625),('space160',160,40,.003125,.0625),
        ('joint320',320,80,.0015625,.03125)]


def main():
    disks();archive=ROOT/'validation/source_archive';archive.mkdir(exist_ok=True)
    (archive/f'radial_model_{MODEL_SHA}.py').write_bytes(MODEL_BYTES)
    checks=[]
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        records={}
        levels=LEVELS+([('joint640',640,160,.00078125,.015625)] if case=='sustainer_cf' else [])
        for tag,nph,ncase,dt,post in levels:
            p=ROOT/'validation/radial'/f'{case}_pulse7_resolved_{tag}.json'
            if p.exists():
                records[tag]=json.loads(p.read_text());continue
            cfg=json.loads((TMP/'runs'/f'{case}_pulse7_n80_dt0125'/'config.json').read_text())
            cfg['geometry'].update(phenolic_radial_rows=nph,aluminium_radial_rows=ncase)
            cfg.update(macro_dt_s=dt,post_pulse_macro_dt_s=post)
            m=RadialModel(cfg)
            state,history,snap=m.run(127,dt=dt,post_dt=post,record_dt=.25,
                targets=[.1,1,2,5,7,10,20,30,60,90,127],check=host_check,stop_at_property_limit=True)
            peaks={key:max(history,key=lambda a:a[key]) for key in ['interface_C','outer_C']}
            result=dict(method='Independent radial finite elements; NOT native ANSYS',configuration=cfg,
                model_sha256=MODEL_SHA,qualification='Exploratory seven-second pulse and ambient cooling; property flag is not structural failure',
                eligible_for_motor_lifetime=False,final=history[-1],history=history,
                sampled_peaks={k:dict(temperature_C=v[k],time_s=v['time_s']) for k,v in peaks.items()},
                event_bracket_s=m.event_bracket,property_limit_bracket_s=m.property_bracket,
                max_energy_relative_error=m.max_energy_error,max_mass_relative_error=m.max_mass_error,
                max_retained_char_fraction_of_initial_mass=m.max_retained_fraction,
                profiles={str(t):dict(radius_m=m.r.tolist(),temperature_C=s.T.tolist(),
                    mean_conversion=s.alpha.mean(axis=1).tolist(),removed_rows=s.layer) for t,s in snap.items()})
            atomic(p,result);records[tag]=result
            print(json.dumps(dict(case=case,level=tag,final=result['final'],peaks=result['sampled_peaks'])),flush=True)
        pairs=[('native_schedule','half_time'),('half_time','quarter_time'),('quarter_time','space160'),('space160','joint320')]
        if case=='sustainer_cf':pairs.append(('joint320','joint640'))
        for coarse,fine in pairs:
            a,b=records[coarse],records[fine]
            cp=a['property_limit_bracket_s'];fp=b['property_limit_bracket_s']
            same_horizon=abs(a['final']['time_s']-b['final']['time_s'])<1e-8
            # Censored histories are compared by flag time, never labelled peaks.
            peak_delta={key:b['sampled_peaks'][key]['temperature_C']-a['sampled_peaks'][key]['temperature_C'] for key in ['interface_C','outer_C']} if same_horizon and cp is None and fp is None else None
            checks.append(dict(case=case,coarse=coarse,fine=fine,
                scope_time_relative_change=abs(fp[1]/cp[1]-1) if cp and fp else None,
                same_end_time=same_horizon,sampled_peak_difference_K=peak_delta,
                retained_mesh_difference_mm=b['final']['remaining_mm']-a['final']['remaining_mm'],
                both_property_censored=bool(cp and fp),both_complete=bool(same_horizon and not cp and not fp)))
        atomic(ROOT/'validation/pulse_resolution.json',dict(complete=len(checks)==17,independent_only=True,
            qualification='Flag-limited histories do not establish a later cooling peak or lifetime',comparisons=checks))


if __name__=='__main__':main()

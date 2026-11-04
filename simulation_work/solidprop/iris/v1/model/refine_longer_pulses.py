"""Refine the previously coarse 20/60-second independent exposure screens."""
import hashlib
import json
from radial_model import RadialModel
from ops import ROOT,atomic,disks,host_check


def main():
    disks();source=(ROOT/'model/radial_model.py').read_bytes();sha=hashlib.sha256(source).hexdigest()
    (ROOT/'validation/source_archive'/f'radial_model_{sha}.py').write_bytes(source)
    comparisons=[]
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        for pulse in [20,60]:
            records=[]
            for n,nc,dt,post in [(160,40,.0015625,.03125),(320,80,.00078125,.015625)]:
                path=ROOT/'validation/radial'/f'{case}_pulse{pulse}_refined_n{n}.json'
                if path.exists():d=json.loads(path.read_text())
                else:
                    cfg=json.loads((ROOT/'configs'/f'{case}.json').read_text())
                    cfg['geometry'].update(phenolic_radial_rows=n,aluminium_radial_rows=nc)
                    cfg['heating'].update(pulse_duration_s=pulse,post_pulse_h_W_m2_K=8.)
                    cfg.update(end_time_s=pulse+300,macro_dt_s=dt,post_pulse_macro_dt_s=post)
                    m=RadialModel(cfg)
                    s,h,_=m.run(pulse+300,dt=dt,post_dt=post,record_dt=.25,targets=[pulse],check=host_check,stop_at_property_limit=True)
                    d=dict(method='Independent radial finite elements; NOT native ANSYS',configuration=cfg,model_sha256=sha,
                        eligible_for_motor_lifetime=False,qualification='Hypothetical imposed pulse, censored at material-scope flag; no actual firing history inferred',
                        final=h[-1],history=h,event_bracket_s=m.event_bracket,property_limit_bracket_s=m.property_bracket,
                        sampled_maxima={k:dict(temperature_C=max(a[k] for a in h),time_s=max(h,key=lambda a:a[k])['time_s']) for k in ['interface_C','outer_C']},
                        max_energy_relative_error=m.max_energy_error,max_mass_relative_error=m.max_mass_error)
                    atomic(path,d);print(case,pulse,n,d['final'],flush=True)
                records.append(d)
            a,b=records;ap=a['property_limit_bracket_s'];bp=b['property_limit_bracket_s']
            timechange=abs(bp[1]/ap[1]-1) if ap and bp else None
            peakdiff={k:b['sampled_maxima'][k]['temperature_C']-a['sampled_maxima'][k]['temperature_C'] for k in ['interface_C','outer_C']} if not ap and not bp else None
            thick=abs(b['final']['remaining_mm']-a['final']['remaining_mm']);tol=max(.02,10*b['configuration']['geometry']['phenolic_thickness_m'])
            comparisons.append(dict(case=case,pulse_s=pulse,coarse_cells=160,fine_cells=320,
                scope_time_relative_change=timechange,sampled_peak_difference_K=peakdiff,remaining_difference_mm=thick,
                thickness_tolerance_mm=tol,flag_before_heating_ends=bool(bp and bp[1]<pulse),
                passed=bool(thick<=tol and ((timechange is not None and timechange<.05) or (peakdiff is not None and max(abs(v) for v in peakdiff.values())<5)))))
            atomic(ROOT/'validation/longer_pulse_refinement.json',dict(complete=len(comparisons)==8,independent_only=True,comparisons=comparisons))


if __name__=='__main__':main()

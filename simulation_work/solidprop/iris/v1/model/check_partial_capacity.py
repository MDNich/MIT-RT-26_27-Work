"""Independent capacity-only diagnostic; not a conservative ablation model.

The existing optional variant subtracts consumed surface-char density from heat
capacity only. It isolates retained-cell storage sensitivity; unchanged geometry,
conductivity and source terms prevent treating it as physical validation.
"""
import hashlib,json
from radial_model import RadialModel
from ops import ROOT,atomic,disks,host_check


def main():
    disks();sources={}
    for name in ['radial_model.py','coupler.py']:
        b=(ROOT/'model'/name).read_bytes();sha=hashlib.sha256(b).hexdigest()
        (ROOT/'validation/source_archive'/f'{name[:-3]}_{sha}.py').write_bytes(b);sources[name]=sha
    checks=[]
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        for n,nc,dt,post in [(80,20,.003125,.0625),(160,40,.003125,.0625),(320,80,.0015625,.03125)]:
            pair=[]
            for partial in [False,True]:
                path=ROOT/'validation/radial'/f'{case}_capacity7_n{n}_{"reduced" if partial else "retained"}.json'
                if path.exists():d=json.loads(path.read_text())
                else:
                    c=json.loads((ROOT/'configs'/f'{case}.json').read_text());end=127 if case.startswith('sustainer') else 300
                    c['geometry'].update(phenolic_radial_rows=n,aluminium_radial_rows=nc)
                    c['heating'].update(pulse_duration_s=7.,post_pulse_h_W_m2_K=8.)
                    c.update(end_time_s=end,macro_dt_s=dt,post_pulse_macro_dt_s=post)
                    m=RadialModel(c,partial_capacity=partial)
                    s,h,_=m.run(end,dt=dt,post_dt=post,record_dt=.25,check=host_check,stop_at_property_limit=True)
                    d=dict(independent_only=True,eligible_for_motor_lifetime=False,partial_capacity_diagnostic=partial,
                        qualification='Capacity-only numerical diagnostic, not a physically conservative removal model or a safety bound',
                        configuration=c,source_hashes=sources,final=h[-1],history=h,scope_bracket_s=m.property_bracket,
                        event_bracket_s=m.event_bracket,max_retained_char_fraction_of_initial_mass=m.max_retained_fraction,
                        max_energy_relative_error=m.max_energy_error,max_mass_relative_error=m.max_mass_error,
                        sampled_peaks={k:dict(value=max(x[k] for x in h),time_s=max(h,key=lambda a:a[k])['time_s']) for k in ['interface_C','outer_C']})
                    atomic(path,d)
                pair.append(d)
            a,b=pair;af=a['scope_bracket_s'];bf=b['scope_bracket_s']
            checks.append(dict(case=case,phenolic_cells=n,case_cells=nc,dt_s=dt,post_dt_s=post,
                retained_capacity_end_s=a['final']['time_s'],reduced_capacity_end_s=b['final']['time_s'],
                scope_time_relative_change=(bf[1]/af[1]-1) if af and bf else None,
                stop_type_matches=bool(af)==bool(bf),remaining_difference_mm=b['final']['remaining_mm']-a['final']['remaining_mm'],
                casing_peak_differences_K={k:b['sampled_peaks'][k]['value']-a['sampled_peaks'][k]['value'] for k in ['interface_C','outer_C']} if not af and not bf else None,
                max_retained_char_mass_fraction=a['max_retained_char_fraction_of_initial_mass']))
            atomic(ROOT/'validation/partial_capacity_resolution.json',dict(complete=len(checks)==12,independent_only=True,
                qualification='This perturbs capacity only; it is not a conservative enthalpy remap, physical calibration or a rigorous bound.',comparisons=checks))
            print(case,n,checks[-1],flush=True)

if __name__=='__main__':main()

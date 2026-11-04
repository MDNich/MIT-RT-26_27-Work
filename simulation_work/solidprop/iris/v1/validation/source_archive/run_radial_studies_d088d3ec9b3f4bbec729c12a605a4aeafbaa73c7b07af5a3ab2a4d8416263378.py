"""Independent mesh/time/exposure studies, explicitly separate from ANSYS."""
import argparse
import hashlib
import json
from pathlib import Path
from radial_model import RadialModel
from ops import ROOT,host_check,atomic

def run(case,n,dt,end,tag,partial=False,pulse=None,overrides=None,stop_at_property_limit=True):
    host_check()
    cfg=json.loads((ROOT/'configs'/f'{case}.json').read_text())
    for section,values in (overrides or {}).items():cfg[section].update(values)
    if pulse is not None:cfg['heating']['pulse_duration_s']=pulse
    path=ROOT/'validation/radial'/f'{case}_{tag}.json';path.parent.mkdir(exist_ok=True)
    if path.exists():
        print('Already recorded',path.name,flush=True);return json.loads(path.read_text())
    m=RadialModel(cfg,rows=n,case_rows=n,partial_capacity=partial)
    s,h,ss=m.run(end,dt=dt,record_dt=max(.1,end/500),check=host_check,stop_at_property_limit=stop_at_property_limit)
    result=dict(method='Independent radial finite-element calculation; NOT native ANSYS output',
                configuration=cfg,phenolic_rows=n,case_rows=n,dt_ceiling_s=dt,partial_capacity_diagnostic=partial,
                end_time_s=end,event_bracket_s=m.event_bracket,property_limit_bracket_s=m.property_bracket,
                stop_at_property_limit=stop_at_property_limit,eligible_for_motor_lifetime=False,
                qualification='Exploratory surrogate, not physically calibrated; property threshold is not structural failure',final=h[-1],history=h,
                max_energy_relative_error=m.max_energy_error,max_mass_relative_error=m.max_mass_error,
                max_retained_char_fraction_of_initial_mass=m.max_retained_fraction,steps=m.steps,
                model_sha256=hashlib.sha256((ROOT/'model/radial_model.py').read_bytes()).hexdigest())
    atomic(path,result)
    print(json.dumps(dict(run=path.stem,final=h[-1],event=m.event_bracket,steps=m.steps)),flush=True)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['mesh7','endurance','pulse','sensitivity']);a=p.parse_args()
    cases=['sustainer_al','sustainer_cf','booster_al','booster_cf']
    if a.mode=='mesh7':
        for case in cases:
            for n in [20,40,80,160]:run(case,n,.0125,7,f'mesh7_n{n}')
            run(case,80,.00625,7,'mesh7_n80_halfdt')
    elif a.mode=='endurance':
        for case in cases:
            for n in [20,40,80,160]:run(case,n,.0125,300,f'property_limit_n{n}')
            run(case,80,.00625,300,'property_limit_n80_halfdt')
            run(case,80,.00625,300,'property_limit_n80_partial_capacity',partial=True)
    elif a.mode=='pulse':
        for case in cases:
            for pulse in [7,20,60]:run(case,80,.025,pulse+120,f'pulse{pulse}',pulse=pulse)
    else:
        for case in cases:
            for h in [500,2000]:run(case,80,.025,300,f'h{h}',overrides={'heating':{'h0_W_m2_K':h}})
            for eps in [.1,.3]:run(case,80,.025,300,f'radiation{eps}',overrides={'heating':{'hot_effective_emissivity':eps}})
            for scale in [.5,2.]:
                run(case,80,.025,300,f'charcost{scale}',overrides={'char_law':{'effective_endothermic_cost_J_kg':35e6*scale}})

if __name__=='__main__':main()

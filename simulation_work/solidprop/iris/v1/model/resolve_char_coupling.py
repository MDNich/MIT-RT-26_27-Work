"""Separate explicit surface-coupling time error from radial mesh error."""
import argparse
import json
from run_radial_studies import run
from ops import ROOT,atomic


def main():
    p=argparse.ArgumentParser();p.add_argument('case',choices=['sustainer_al','booster_cf']);case=p.parse_args().case
    base=json.loads((ROOT/'validation/radial'/f'{case}_fine_h2000.json').read_text())
    results={}
    for tag,n,dt in [('n320_quarter',320,.0001953125),('n320_eighth',320,.00009765625),('n640',640,.000048828125)]:
        d=run(case,n,dt,300,'coupling_h2000_'+tag,overrides={'_root':base['configuration']})
        assert d['property_limit_bracket_s'] is not None
        results[tag]=dict(cells=n,dt_s=dt,scope_bracket_s=d['property_limit_bracket_s'],remaining_mm=d['final']['remaining_mm'],hot_C=d['final']['hot_C'])
        checks=[]
        for a,b,kind in [('n320_quarter','n320_eighth','time only'),('n320_quarter','n640','joint, dt scaled with radial pitch squared')]:
            if a not in results or b not in results:continue
            A,B=results[a],results[b];td=abs(B['scope_bracket_s'][1]/A['scope_bracket_s'][1]-1)
            rd=abs(B['remaining_mm']-A['remaining_mm']);tol=max(.02,10*base['configuration']['geometry']['phenolic_thickness_m'])
            checks.append(dict(coarse=a,fine=b,comparison=kind,relative_time_change=td,remaining_difference_mm=rd,thickness_tolerance_mm=tol,passed=bool(td<.05 and rd<=tol)))
        atomic(ROOT/'validation'/f'char_coupling_resolution_{case}.json',dict(complete=len(results)==3,
            independent_only=True,not_burnthrough=True,
            qualification='Diagnostic for explicit surface-coupling sensitivity under doubled heating; no material law is calibrated by this exercise',results=results,comparisons=checks))


if __name__=='__main__':main()

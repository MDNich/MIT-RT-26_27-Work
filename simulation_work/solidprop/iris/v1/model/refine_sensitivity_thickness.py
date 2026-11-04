"""Resolve remaining-thickness differences separately from scope-event timing."""
import json
from run_radial_studies import run
from ops import ROOT,atomic


def main():
    summary=json.loads((ROOT/'validation/input_sensitivity_refinement.json').read_text())
    checks=[]
    for record in summary['results']:
        case=record['case'];tag=record['scenario']
        base=json.loads((ROOT/'validation/radial'/f'{case}_fine_refined_{tag}.json').read_text())
        tol=max(.02,10*base['configuration']['geometry']['phenolic_thickness_m'])
        if abs(record['retained_thickness_change_mm'])<=tol:continue
        refined=run(case,320,.00078125,300,f'fine_thickness320_{tag}',overrides={'_root':base['configuration']})
        assert refined['property_limit_bracket_s'] is not None
        thickness=refined['final']['remaining_mm']-base['final']['remaining_mm']
        timing=abs(refined['final']['time_s']/base['final']['time_s']-1)
        checks.append(dict(case=case,scenario=tag,coarse_cells=160,fine_cells=320,
            fine_scope_bracket_s=refined['property_limit_bracket_s'],fine_remaining_mm=refined['final']['remaining_mm'],
            relative_time_change=timing,remaining_difference_mm=thickness,thickness_tolerance_mm=tol,
            passed=bool(abs(thickness)<=tol and timing<.05)))
        atomic(ROOT/'validation/sensitivity_thickness_refinement.json',dict(complete=False,independent_only=True,results=checks))
    atomic(ROOT/'validation/sensitivity_thickness_refinement.json',dict(complete=True,independent_only=True,
        qualification='Resolution at the property-scope flag; never an exhaustion or structural-failure prediction',results=checks))


if __name__=='__main__':main()

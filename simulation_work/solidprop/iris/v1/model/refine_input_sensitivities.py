"""Numerical spot checks of the strongest independent input perturbations."""
import json
from run_radial_studies import run
from ops import ROOT, atomic


def main():
    records=[]
    for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
        tags=['h2000','phenolic_k_0.8']
        if case.endswith('_cf'): tags.append('cf_nasa_reference')
        for tag in tags:
            source=ROOT/'validation/radial'/f'{case}_fine_{tag}.json'
            base=json.loads(source.read_text())
            cfg=base['configuration']
            cfg['provenance']['resolution_check']='Joint 160-cell/0.0015625-second refinement of the 80-cell/0.003125-second sensitivity; not physical calibration'
            refined=run(case,160,.0015625,300,f'fine_refined_{tag}',overrides={'_root':cfg})
            assert base['property_limit_bracket_s'] and refined['property_limit_bracket_s']
            change=abs(refined['final']['time_s']/base['final']['time_s']-1)
            records.append(dict(case=case,scenario=tag,
                base_scope_bracket_s=base['property_limit_bracket_s'],
                refined_scope_bracket_s=refined['property_limit_bracket_s'],
                relative_time_change=change,target_5_percent_passed=change<.05,
                retained_thickness_change_mm=refined['final']['remaining_mm']-base['final']['remaining_mm']))
            atomic(ROOT/'validation/input_sensitivity_refinement.json',dict(
                complete=len(records)==10,not_burnthrough=True,
                qualification='Independent numerical spot checks; scenarios not listed here were not individually refined',
                results=records))


if __name__=='__main__': main()

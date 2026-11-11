"""Check the law-comparison reader against the already audited bare and snug paths."""
import numpy as np

from compare_pull_laws import loading_curve, at_first_crossing
from audit_local import ROOT, read
from film_identity import digest, write_json
from snug_directional_result import refined_tab_crossing


def run():
    audit=ROOT/'validation/snug125'
    bare_file=ROOT/'validation/pull_laws/bare.json'
    bare=read(bare_file)
    results={}
    for branch,damage in [('bare',False),('bare',True),
                          ('snug125_nylon',False),('snug125_aluminium',False)]:
        rows,source=loading_curve(branch,damage)
        case=source['case']
        target=bare['bare_control_force_N']
        crossing=at_first_crossing(rows,'cell_fx_N',target)
        if branch=='bare':
            assert source==bare['sources'][case]
            assert crossing==bare['curves'][case]['at_bare_control_force']
            reference=bare_file
        else:
            reference=audit/(case+'_comparison.json')
            previous=read(reference)
            endpoint=previous['equal_travel']['cased']
            assert rows['native_set'][-1]==endpoint['set']
            assert np.isclose(rows['ux_mm'][-1],endpoint['ux_mm'],rtol=0,atol=1e-10)
            assert np.isclose(rows['cell_fx_N'][-1],endpoint['cell_force_N'],rtol=0,atol=1e-8)
            expected=previous['equal_load']['cased']
            assert [r['native_set'] for r in crossing['bracket']]==expected['native_sets']
            assert np.isclose(crossing['travel_mm'],expected['travel_mm'],rtol=0,atol=1e-10)
            assert source['criteria_sha256']['refined_tab_submodel']==previous['refined_tab_crossing']['submodel_sha256']
            if branch=='snug125_nylon':
                termination=audit/(case+'_termination.json')
                assert source['criteria_sha256']['accepted_equilibrium_prefix']==digest(termination)
                assert previous['accepted_equilibrium_prefix']==read(termination)['first_contiguous_balance_pass_states']
        results[case]=dict(last_native_set=int(rows['native_set'][-1]),
                          last_screened_travel_mm=float(rows['ux_mm'][-1]),
                          equal_load=crossing,source=source,reference_sha256=digest(reference))
    excluded=[]
    for branch in ('snug125_nylon','snug125_aluminium'):
        for suffix in ('_damage_cont_nominal_pin1_m15','_lateral_friction_locked_minus_pin1_m15'):
            case=branch+suffix
            assert refined_tab_crossing(case,'not-the-forward-input',{}) is None
            excluded.append(case)
    record=dict(reader_sha256=digest(ROOT/'model/compare_pull_laws.py'),
                check_sha256=digest(ROOT/'model/check_pull_law_scope.py'),checked_paths=results,
                no_forward_bound_transfer=excluded,
                scope='The law-comparison reader reproduces existing bare curves and audited forward bounds. '
                      'It excludes rejected nylon equilibria and retains the earlier refined PLA limits. '
                      'Damage and reverse decks retain their own screens. No new solve or material law was introduced.')
    write_json(audit/'pull_law_reader_scope_check.json',record)
    print({k:v['last_screened_travel_mm'] for k,v in results.items()})


if __name__=='__main__':
    run()

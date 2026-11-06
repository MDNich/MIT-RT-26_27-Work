"""Recover the independent chemical energy inventory and deposited heat at exhaustion.

This postprocessor reads the hashed, completed finite-volume and nodal FE
scenarios. It neither integrates a transient nor dispatches a native job.
"""
from pathlib import Path

import backing_film_campaign as film
from continuous_heating_campaign import digest
from ops import ROOT, TMP, StorageLimitError, atomic, disks, stop_runs, utc
from sector_exposure import unpack
from sector_wall import Sector

OUT = ROOT/'validation/liner_exhaustion_energy.json'


def verified(path, sha):
    if digest(path) != sha:
        raise ValueError(f'Input differs from its audit: {path}')
    return film.read(path)


def records(case, h, parent, result, sector):
    if h == '1000':
        module = film.MATERIALS[parent['configuration']['case_material']]
        fv = module.OUT/(parent['tag']+'.json')
        fv_sha = result['sha256']
        fe = TMP/'sector_reduction'/sector['sources']['check_sector_exposure'][:12]/(case+'_160_0.02.json')
        fe_sha = sector['cases'][case]['runs'][-1]['record_sha256']
        fe_setting, fe_state = 'settings', 'record'
    else:
        assert result['final_FV_pairs_pass']
        fv = film.DATA/(result['reported_FV_tag']+'.json')
        refinements = result['additional_FV_checks'].get('time')
        reference = refinements['checks'][-1]['record'] if refinements else result['FV_records']['fine']
        fv_sha = reference['sha256']
        fe = film.WORK/'finite_element_checks'/(case+'_h'+h+'.json')
        fe_sha = result['reference_FE']['record_sha256']
        fe_setting, fe_state = 'input', 'state'
    cells = verified(fv, fv_sha)
    nodes = verified(fe, fe_sha)
    assert cells['event_bracket_s'][1] == result['event_s']
    return cells, nodes[fe_setting], nodes[fe_state], dict(FV=fv_sha, FE=fe_sha)


def mass_and_reaction(m0, virgin, char, gas, products, reaction, y, lp, lc):
    converted = m0-virgin
    return max(abs(gas-(1-y)*converted)/m0, abs(char+products-y*converted)/m0,
               abs(reaction-lp*converted-lc*products)/(m0*(lp+y*lc)))


def energy_budget(film_heat, char_cost, pyrolysis, liner_products, case_heat, case_gas, case_reaction, outside, area):
    terms = dict(char_removal=char_cost, pyrolysis=pyrolysis, liner_products=liner_products,
                 stored_in_case=case_heat, casing_gas=case_gas, casing_net_reaction=-case_reaction,
                 ambient_loss=outside)
    if abs(sum(terms.values())/film_heat-1) > 1e-7:
        raise ValueError('Terminal heat inventory does not close')
    return dict(film_MJ_m2=film_heat/(area*1e6),
                partition_MJ_m2={k:v/(area*1e6) for k,v in terms.items()},
                char_percent=100*char_cost/film_heat)


def analyze(cells, settings, nodes):
    cfg = settings['configuration']
    geom, material = cfg['geometry'], cfg['material']
    ri, ro = geom['inner_radius_m'], geom['phenolic_outer_radius_m']
    density = material['virgin_reference_density_kg_m3']
    m0 = density*(ro-ri)*(ro+ri)/2
    lp, lc = material['pyrolysis_enthalpy_J_kg'], cfg['char_law']['effective_endothermic_cost_J_kg']
    y = material['char_reference_density_kg_m3']/density
    rows = cells['history']
    assert abs(rows[0]['virgin_kg_per_rad_m']-m0) < 1e-12
    assert rows[0]['solid_sensible_J_per_rad_m'] == 0
    assert rows[-1]['char_kg_per_rad_m'] == rows[-1]['virgin_kg_per_rad_m'] == 0
    err = 0.
    for r in rows:
        l = r['ledger']
        err = max(err, mass_and_reaction(m0,r['virgin_kg_per_rad_m'],r['char_kg_per_rad_m'],
                        l['bulk_gas']+l['face_gas'],l['char_products'],l['bulk_reaction']+l['face_reaction'],y,lp,lc))
    end = rows[-1]; led = end['ledger']
    assert led['radiation_heat'] == 0
    fv = energy_budget(led['film_heat'],y*m0*lc,m0*lp,led['bulk_gas_heat']+led['face_products_heat'],
                       end['solid_sensible_J_per_rad_m'],led.get('backing_gas_heat',0.),led.get('backing_reaction_heat',0.),
                       led['outer_loss'],ri)
    s = nodes['stats']['sums']
    state = unpack(nodes['state'])
    wall = Sector(cfg,settings['n'],settings['nc'])
    initial_mass, _, initial_heat = wall.inventory(wall.initial())
    end_mass, _, end_heat = wall.inventory(state)
    assert abs(initial_mass-m0) < 1e-12 and end_mass == 0 and initial_heat == 0 and s['radiation'] == 0
    err = max(err,mass_and_reaction(m0,0.,0.,s['bulk_gas']+s['front_gas'],s['char_products'],
                                    s['bulk_cost']+s['face_cost'],y,lp,lc))
    if err > 1e-8:
        raise ValueError('Species or chemical energy differs from initial-inventory identity')
    fe = energy_budget(s['film'],y*m0*lc,m0*lp,s['bulk_gas_h']+s['face_products_h'],end_heat,s['back_gas_h'],
                       s['back_release'],s['outer'],ri/wall.facet)
    sampled_peak = max((r['face_C'],r['time_s']) for r in rows if r['remaining_mm']>0)
    return dict(event_s=end['time_s'],initial_virgin_kg_per_m2=m0/ri,yield_kg_char_per_kg_virgin=y,
                pyrolysis_J_kg_virgin=lp,removal_J_kg_char=lc,analytic_reaction_MJ_m2=m0/ri*(lp+y*lc)/1e6,
                checked_FV_times=len(rows),max_mass_or_chemical_energy_fractional_error=err,
                hottest_sampled_live_face_C=sampled_peak[0],hottest_sample_time_s=sampled_peak[1],
                mean_film_per_original_area_MW_m2=fv['film_MJ_m2']/end['time_s'],FV=fv,FE=fe,
                FE_minus_FV_film_percent=100*(fe['film_MJ_m2']/fv['film_MJ_m2']-1),
                FE_minus_FV_char_share_points=fe['char_percent']-fv['char_percent'])


def main():
    disks()
    _, plan_sha, parents = film.verified_plan()
    evidence = film.read(film.PROOF)
    sector_path = ROOT/'validation/sector_exposure_reduction.json'
    sector = film.read(sector_path)
    assert evidence['plan_sha256'] == plan_sha and sector['passed']
    assert evidence['auditor_sha256'] == digest(ROOT/'model/audit_backing_film.py')
    for name, sha in sector['sources'].items():
        assert digest(ROOT/f'model/{name}.py') == sha
    results = {}
    for case, parent in parents.items():
        results[case] = {}
        for h in ('500','1000','2000'):
            result = evidence['results'][case][h]
            cells,settings,nodes,sources = records(case,h,parent,result,sector)
            cfg = settings['configuration']
            original = parent['configuration']
            assert cfg['case_id'] == original['case_id'] and cfg['heating']['h0_W_m2_K'] == int(h)
            assert cfg['geometry'] == original['geometry'] and cfg['material'] == original['material']
            assert cfg['char_law'] == original['char_law']
            r = analyze(cells,settings,nodes)
            results[case][h] = dict(r,source_sha256=sources)
            print(case,h,round(r['FV']['char_percent'],2),round(r['FE_minus_FV_film_percent'],4))
    atomic(OUT,dict(utc=utc(),passed=True,source_sha256=digest(Path(__file__)),film_audit_sha256=digest(film.PROOF),
                    sector_audit_sha256=digest(sector_path),cases=results,
                    scope='Conditional model energy inventories per original exposed area. No native solves or material calibration.'))


if __name__ == '__main__':
    try: main()
    except StorageLimitError as exc:
        stop_runs(str(exc))
        raise

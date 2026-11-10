"""Verify each nickel-law comparison and reduce the matched native bare and snug histories at closure."""
import argparse
import re

import numpy as np

from audit_local import ROOT,read
from compare_pull_laws import at_first_crossing,loading_curve
from film_identity import digest,verified,write_json
from stage_snug_fit import AUDIT,INPUTS,STEP_HASH

NOMINAL='damage_cont_nominal'
CASES=('bare','snug125_nylon','snug125_aluminium')
GRID=(.1,.3,.6)
EVOLUTION=(.03,.12,.24)


def law(deck):
    start=deck.index(b'TB,CDM,1,,2,DUCTILE\n')
    stop=deck.index(b'TB,CDM,1,,,DCAP\n',start)
    strain,evolution=deck[start:stop].split(b'TB,CDM,1,,,LINDMG\nTBDATA,1,')
    rows=np.array([(float(a),float(b)) for a,b in re.findall(rb'(?m)^TBPT,DEFI,([^,\n]+),([^\n]+)$',strain)])
    assert rows.shape==(13,2) and np.all(np.diff(rows[:,0])>0) and np.all(rows[:,1]>0)
    assert np.array_equal(rows[:2,1],[1.e6,1.e6]) and rows[2,0]==0
    return (rows,float(evolution)),deck[:start]+deck[stop:]


def prepare():
    base=read(ROOT/'validation/local_jobs.json')
    config=read(ROOT/'validation/local_inputs.json')
    registries=[AUDIT/'local_inputs_m15.json',AUDIT/'local_sensitivity_inputs_m15.json']
    cased={k:v for path in registries for k,v in read(path).items()}
    sources=sorted({q['source'] for q in cased.values() if q['source'].startswith('damage_cont')})
    assert len(sources)==12
    cases={}
    for branch in CASES:
        catalog=base if branch=='bare' else cased
        profile={}
        for source in [NOMINAL,*[s for s in sources if s!=NOMINAL]]:
            name=f'{branch}_{source}'+('' if branch=='bare' else '_pin1_m15')
            proof=catalog[name];folder=INPUTS/name
            verified(folder/'local_job.json',proof['spec_sha256'])
            job=read(folder/'local_job.json')
            assert job['case']==name and job['source']==source and job['files']['model.inp']==proof['input_sha256']
            for filename,sha in job['files'].items():verified(folder/filename,sha)
            if branch!='bare':
                assert job['step_sha256']==STEP_HASH and job['tab_standoff_mm']==1.25 and job['size_mm']==1.5
                assert job['case_mesh_sha256']==proof['mesh_sha256']
            cfg_file=ROOT/'.runtime/local_inputs'/source/'config.json'
            verified(cfg_file,config[source]['files']['config.json'])
            cfg=read(cfg_file);deck=(folder/'model.inp').read_bytes()
            (points,uf),outside=law(deck)
            assert uf==cfg['uf_mm'] and points[2,1]==cfg['eps0']
            if source==NOMINAL:
                full=deck;reference=outside;ref_points=points
            assert np.array_equal(points[:,0],ref_points[:,0])
            assert np.allclose(points[2:,1]/points[2,1],ref_points[2:,1]/ref_points[2,1],rtol=2e-8,atol=0)
            if source==NOMINAL or re.fullmatch(r'damage_cont_e\d+u\d+',source):
                assert outside==reference
                kind='material_grid'
            elif source=='damage_cont_force5em5':
                marker=b'CNVTOL,F,,5e-05,,1\n'
                assert deck.count(marker)==1 and deck.replace(marker,b'')==full
                kind='pull_force_tolerance'
            elif source=='damage_continuous_proof':
                short=b'*DO,JJ,1,2\n';long=b'*DO,JJ,1,32\n'
                assert deck.count(short)==1 and deck.replace(short,long)==full
                kind='independent_short_loading_proof'
            else:
                assert source=='damage_cont_fine' and cfg['elements']>read(ROOT/'.runtime/local_inputs'/NOMINAL/'config.json')['elements']
                assert np.array_equal(points,ref_points) and uf==.12
                kind='refined_nickel_mesh'
            profile[source]=dict(case=name,control=kind,eps0=float(points[2,1]),evolution_length_mm=uf,
                total_requested_lateral_travel_mm=cfg['displacement_mm'],nickel_shell_elements=cfg['elements'],
                input_sha256=proof['input_sha256'],job_spec_sha256=proof['spec_sha256'],config_sha256=digest(cfg_file),
                nickel_mesh_sha256=config[source]['files']['mesh.json'])
        assert {(r['eps0'],r['evolution_length_mm']) for r in profile.values() if r['control']=='material_grid'}=={
            (x,y) for x in GRID for y in EVOLUTION}
        cases[branch]=profile
    for source in sources:
        assert len({cases[b][source]['nickel_mesh_sha256'] for b in CASES})==1
        assert len({cases[b][source]['config_sha256'] for b in CASES})==1
    result=dict(cases=cases,source_registries={p.name:digest(p) for p in registries},
        scope='Input identities only. Each material-grid comparison retains its complete native deck outside the '
              'nickel damage-initiation and evolution cards. Changing these laws requires preserving their individual histories.')
    write_json(AUDIT/'damage_family_inputs.json',result)


def result_file(case):
    paths=[p for group in ('local','partial_local') if (p:=ROOT/'validation'/group/(case+'.json')).is_file()]
    assert len(paths)<=1
    return paths[0] if paths else None


def paired_metrics(curves,target):
    travel=min(r['ux_mm'][-1] for r in curves)
    travel_brackets={k:at_first_crossing(r,'ux_mm',travel) for k,r in zip(('bare','snug'),curves,strict=True)}
    assert all(travel_brackets.values())
    return dict(common_travel_mm=float(travel),equal_force_reference_N=float(target),at_common_travel=travel_brackets,
        at_reference_force={k:at_first_crossing(r,'cell_fx_N',target) for k,r in zip(('bare','snug'),curves,strict=True)})


def compare_case(case):
    families=read(AUDIT/'damage_family_inputs.json')['cases']
    matches=[(b,s,v) for b in CASES[1:] for s,v in families[b].items() if v['case']==case]
    (branch,source,spec),=matches
    bare=families['bare'][source]
    proofs=[result_file(s['case']) for s in (bare,spec)]
    if any(p is None for p in proofs):
        return
    for p,s in zip(proofs,(bare,spec),strict=True):
        verdict=read(p);folder=ROOT/'.runtime/archive'/verdict['campaign']/s['case']
        verified(folder/'local_job.json',s['job_spec_sha256'])
        assert read(folder/'local_job.json')['files']['model.inp']==s['input_sha256']
    scope_file=ROOT/'validation/pulls'/(case+'_damage_scope.json')
    scope=read(scope_file)
    assert scope['fixture_audit_sha256']==digest(proofs[1])
    stock=read(proofs[0]);assert stock['source']==source
    output=dict(branch=branch,source=source,control=spec['control'],case=case,bare_case=bare['case'],
        fixture_sha256=[digest(p) for p in proofs],inputs_sha256=digest(AUDIT/'damage_family_inputs.json'),
        mounted_material_scope_sha256=digest(scope_file),eps0=spec['eps0'],evolution_length_mm=spec['evolution_length_mm'],
        nickel_model_onset={'bare':stock['damage_onset_bracket'],'snug':scope['nickel_bracket']},
        mounted_first_limit_sets=scope['first_criterion_sets'],mounted_onset_interpretation=scope['interpretation'])
    onset=scope['nickel_bracket']
    limits=scope['first_criterion_sets'].values()
    output['snug_onset_within_recorded_screens']=onset if onset and all(onset[-1]['native_set']<limit for limit in limits) else None
    end=scope['last_station_before_limits']
    if end is not None and end['travel_mm']>0:
        rows=[];sources=[]
        for name in ('bare',branch):
            curve,record=loading_curve(name,True,source=source)
            rows.append(curve);sources.append(record)
        assert sources[0]['mesh_sha256']==sources[1]['mesh_sha256']==spec['nickel_mesh_sha256']
        assert all(r['washer_preload_N']==750 for r in sources)
        ref,ref_source=loading_curve('bare',False)
        output.update(paired_metrics(rows,ref['cell_fx_N'][-1]),
                      bare_bilinear_reference_rst_sha256=ref_source['rst_sha256'],histories=sources)
    else:
        output['comparison_unavailable']='The mounted fixture has no positive lateral station before its first scope limit.'
    output['scope']='First loading crossings on screened native paths. Brackets retain both saved stations. Damage is the section-summary model variable.'
    write_json(AUDIT/(case+'_matched_damage.json'),output)
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','compare'));p.add_argument('case',nargs='?')
    args=p.parse_args()
    if args.action=='prepare':prepare()
    else:compare_case(args.case)

"""Compare loads and travel at common points on the two nominal nickel-fixture histories."""
import argparse

import numpy as np

from audit_local import ROOT, read, table
from film_identity import digest, verified, write_json


def loading_curve(branch, damage, *, source=None):
    source=source or ('damage_cont_nominal' if damage else 'lateral_friction_locked')
    assert damage==source.startswith('damage_')
    suffix='' if branch=='bare' else ('_pin1_m15' if branch.startswith('snug125_') else '_pin1')
    case=f'{branch}_{source}'+suffix
    base=ROOT/'validation'
    verdict_path,=[p for group in ('local','partial_local') if (p:=base/group/(case+'.json')).is_file()]
    proof=read(verdict_path)
    campaign=proof['campaign']
    folder=ROOT/'.runtime/archive'/campaign/case
    receipt=ROOT/'.runtime/receipts'/campaign/case
    ledger=read(receipt/'archived.json')
    hashes={f['name']:f['sha256'] for f in ledger['files']}
    assert (receipt/'released.txt').is_file() and ledger['case']==proof['case']==case and ledger['campaign']==campaign
    spec=read(folder/'local_job.json')
    assert spec['source']==source and spec['cased']==(branch!='bare')
    verified(folder/'model.inp',spec['files']['model.inp'])
    rst=spec['job']+'.rst'
    assert hashes[rst]==proof['rst_sha256']
    verified(folder/rst,hashes[rst])
    cfgdir=ROOT/'.runtime/local_inputs'/source
    original=read(base/'local_inputs.json')[source]['files']
    for filename in ('mesh.json','config.json'):
        verified(cfgdir/filename,original[filename])
    cfg=read(cfgdir/'config.json')
    start=cfg['pull_start_time']
    balance_file=ROOT/'.runtime/post'/campaign/case/'whole_fixture_balance.csv'
    force=table(balance_file)
    filename='set_inventory.csv' if damage else 'history.csv'
    verified(folder/filename,hashes[filename])
    native=table(folder/filename)
    assert np.array_equal(force['native_set'],native['set']) and np.allclose(force['time'],native['time'],rtol=0,atol=1e-7)
    assert np.allclose(force['ux_mm'],native['ux_mm'],rtol=0,atol=1e-7)
    assert np.allclose(force['cell_fx_N'],native['fx_N'],rtol=1e-7,atol=1e-5)
    criteria={}
    if damage:
        strict=base/'damage_balance'/(case+'.json')
        checked=read(strict)
        assert checked['all_states_within_limits'] and checked['rst_sha256']==proof['rst_sha256']
        assert checked['recovered_fixture_balance_sha256']==digest(balance_file)
        assert not proof['nickel_material_scope_exceeded']
        criteria['nickel_force_balance']=digest(strict)
    # Compare from lock through the last contiguous state inside the PLA and contact limits.
    force=force[force['time']>=start-1e-9]
    if branch!='bare':
        mat=base/'pull_material'/(case+'.json')
        material=read(mat)
        contacts=base/'pulls'/(case+'_contact.csv')
        contact=np.genfromtxt(contacts,names=True,delimiter=',',
                usecols=('native_set','pair','max_closed_corner_penetration_mm'))
        contact_proof=read(base/'pulls'/(case+'_contact.json'))
        assert contact_proof['rst_sha256']==material['rst_sha256']==proof['rst_sha256']
        assert material['contact_verdict_sha256']==digest(verdict_path)
        assert np.isclose(contact_proof['max_closed_corner_penetration_mm'],contact['max_closed_corner_penetration_mm'].max())
        full_sets=native['set']
        assert np.array_equal(contact['native_set'],np.repeat(full_sets,2))
        assert np.array_equal(contact['pair'],np.tile([861,862],len(full_sets)))
        bad=[p['native_set'] for key,p in material['first_reference_crossings'].items() if key.startswith('all_')]
        bad.extend(contact['native_set'][contact['max_closed_corner_penetration_mm']>.05])
        if bad:
            force=force[force['native_set']<min(bad)]
        criteria.update(PLA=digest(mat),closed_corners=digest(contacts))
        if damage:
            scope_path=base/'pulls'/(case+'_damage_scope.json')
            scope=read(scope_path)
            assert scope['fixture_audit_sha256']==digest(verdict_path) and scope['contact_table_sha256']==digest(contacts)
            previous=scope['last_station_before_limits']
            if len(force):
                assert previous and previous['native_set']==force['native_set'][-1]
            criteria['threshold_chronology']=digest(scope_path)
    assert len(force) and abs(force['ux_mm'][0])<1e-8 and np.all(np.diff(force['ux_mm'])>0)
    provenance=dict(case=case,campaign=campaign,fixture_sha256=digest(verdict_path),
                    native_history_sha256=hashes[filename],rst_sha256=proof['rst_sha256'],criteria_sha256=criteria,
                    mesh_sha256=original['mesh.json'],washer_preload_N=cfg['preload_N'],
                    nickel_thickness_mm=cfg['thickness_mm'],washer_friction=cfg['mu'],yield_MPa=cfg['yield_MPa'],
                    last_supported_travel_mm=float(force['ux_mm'][-1]))
    return force,provenance


def at_first_crossing(rows,field,target):
    hit=np.flatnonzero(rows[field]>=target-1e-9)
    if not len(hit):
        return None
    upper=int(hit[0])
    exact=abs(rows[field][upper]-target)<1e-9
    if not exact and upper==0:
        return None
    lower=upper if exact else upper-1
    endpoints=[dict(native_set=int(r['native_set']),travel_mm=float(r['ux_mm']),force_N=float(r['cell_fx_N']))
               for r in rows[[lower,upper]]]
    alpha=0. if exact else (target-rows[field][lower])/(rows[field][upper]-rows[field][lower])
    assert 0<=alpha<=1
    return dict(exact_saved_state=bool(exact),bracket=endpoints,
                travel_mm=float((1-alpha)*rows['ux_mm'][lower]+alpha*rows['ux_mm'][upper]),
                force_N=float((1-alpha)*rows['cell_fx_N'][lower]+alpha*rows['cell_fx_N'][upper]))


def compare(branch):
    variants=('bare',) if branch=='bare' else ('bare',branch)
    curves={}
    sources={}
    for v in variants:
        for damage in (False,True):
            rows,source=loading_curve(v,damage)
            curves[source['case']]=rows
            sources[source['case']]=source
    for key in ('mesh_sha256','washer_preload_N','nickel_thickness_mm','washer_friction'):
        assert len({s[key] for s in sources.values()})==1
    travel=min(r['ux_mm'][-1] for r in curves.values())
    force=curves['bare_lateral_friction_locked']['cell_fx_N'][-1]
    results={k:dict(at_common_travel=at_first_crossing(r,'ux_mm',travel),
                    at_bare_control_force=at_first_crossing(r,'cell_fx_N',force)) for k,r in curves.items()}
    assert all(item['at_common_travel'] is not None for item in results.values())
    write_json(ROOT/'validation/pull_laws'/(branch+'.json'),dict(branch=branch,sources=sources,
        common_travel_mm=float(travel),bare_control_force_N=float(force),curves=results,
        scope='First loading crossing, from locked clamps through the supported native range of each positive-X '
              'fixture. Interpolation between adjacent equilibrium states only. Material cards and load increments '
              'differ across the two nickel studies. Rupture is unresolved.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('branch',choices=['bare','stand3_nylon','stand3_aluminium','snug125_nylon','snug125_aluminium'])
    compare(p.parse_args().branch)

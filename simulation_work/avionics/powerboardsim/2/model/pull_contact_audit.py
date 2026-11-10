"""Separate penetrations on closed corners from near-field values on unloaded facets."""
import argparse
import csv
import json

import numpy as np
from ansys.mapdl import reader
from audit_local import read,table,ROOT
from film_identity import digest,verified,write_json
from global_contact import pair_summary


def verify(case,proof_path=None):
    proofs=[ROOT/'validation'/group/(case+'.json') for group in ('local','partial_local')]
    if proof_path is None:
        proof_path, = [p for p in proofs if p.is_file()]
    proof=read(proof_path)
    camp=proof['campaign']
    archive=ROOT/f'.runtime/archive/{camp}/{case}'
    receipt=ROOT/f'.runtime/receipts/{camp}/{case}'
    ledger=read(receipt/'archived.json')
    assert (receipt/'released.txt').is_file() and ledger['case']==case and ledger['campaign']==camp
    hashes={f['name']:f['sha256'] for f in ledger['files']}
    for name in ('local_job.json','case_pairs.csv'):
        verified(archive/name,hashes[name])
    spec=read(archive/'local_job.json')
    assert spec['case']==proof['case']==case and spec['source']==proof['source'] and spec['cased']
    filename=spec['job']+'.rst'
    assert hashes[filename]==proof['rst_sha256']
    verified(archive/filename,hashes[filename])
    raw=reader.read_binary(str(archive/filename));grid=raw.grid
    pairs=table(archive/'case_pairs.csv')
    balance=table(ROOT/f'.runtime/post/{camp}/{case}/whole_fixture_balance.csv')
    expected=np.flatnonzero(raw._resultheader['ls_table'][:,1]!=999999)+1
    assert np.array_equal(balance['native_set'],expected)
    assert np.allclose(balance['time'],raw.time_values[expected-1],atol=1.e-7,rtol=0)
    assert np.array_equal(pairs['set'],np.repeat(expected,2)) and np.array_equal(pairs['pair'],np.tile([861,862],len(expected)))
    rows=[]
    for br in balance:
        k=int(br['native_set'])
        enum,nmisc,_=raw.element_solution_data(k-1,'EMN')
        ee,ect,nodes=raw.element_solution_data(k-1,'ECT')
        for rid in (861,862):
            mask=(grid.cell_data['ansys_etype']==862)&(grid.cell_data['ansys_real_constant']==rid)
            elements=grid.cell_data['ansys_elem_num'][mask]
            idx=np.searchsorted(enum,elements)
            assert np.array_equal(enum[idx],elements)
            # Far-field elements with no saved record have no compressive contact force.
            items=[nmisc[i] for i in idx if nmisc[i] is not None and len(nmisc[i])]
            a=np.stack(items) if items else np.empty((0,45))
            assert a.shape[1]>=45
            closed=a[:,40]>=2
            loaded=a[:,:4]>=2
            corners=pair_summary(k-1,raw.time_values[k-1],elements,ee,ect,nodes)
            assert corners['sliding']+corners['sticking']==np.count_nonzero(loaded.any(axis=1))
            depth=float(a[:,8:12][loaded].max(initial=0.))
            assert np.isclose(depth,corners['loaded_corner_pen_max'],rtol=2.e-6,atol=1.e-9)
            row=pairs[(pairs['set']==k)&(pairs['pair']==rid)]
            assert len(row)==1 and len(elements)==row['elements'][0] and int(closed.sum())==row['closed'][0]
            force=a[:,42:45].sum(axis=0,dtype=float)
            assert np.allclose(force,[row['fx_N'][0],row['fy_N'][0],row['fz_N'][0]],rtol=2e-6,atol=1e-5)
            residual=None
            if rid==861:
                supports=np.array([br['screw_support_N_'+k]+br['neighbor_support_N_'+k] for k in 'xyz'])
                residual=float(np.linalg.norm(force-supports))
                if residual>max(.01,.002*np.linalg.norm(force)):raise ValueError(('Contact vs case supports',k,residual))
            rows.append(dict(native_set=k,ux_mm=float(br['ux_mm']),pair=rid,closed_faces=int(closed.sum()),closed_corner_records=int(loaded.sum()),
                     max_closed_corner_penetration_mm=depth,
                     max_all_corner_value_mm=float(max(0,a[:,8:12].max(initial=0))),
                     active_pair_vs_case_support_residual_N=residual))
    out=ROOT/'validation/pulls';out.mkdir(exist_ok=True)
    active=[r for r in rows if r['pair']==861]
    final=dict(case=case,rst_sha256=proof['rst_sha256'],converged_states=len(active),
            max_closed_corner_penetration_mm=max(r['max_closed_corner_penetration_mm'] for r in rows),
            end_active_closed_corner_penetration_mm=active[-1]['max_closed_corner_penetration_mm'],
            max_unfiltered_corner_value_mm=max(r['max_all_corner_value_mm'] for r in rows),
            max_active_contact_vs_support_force_residual_N=max(r['active_pair_vs_case_support_residual_N'] for r in active))
    (out/(case+'_contact.json')).write_text(json.dumps(final,indent=2)+'\n')
    with (out/(case+'_contact.csv')).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    print(final)
    if spec['source'].startswith('damage_cont'):
        damage_scope(case,camp,proof,proof_path,rows)


def damage_scope(case,campaign,proof,proof_path,contacts):
    base=ROOT/'validation'
    material_path=base/'pull_material'/(case+'.json')
    material=read(material_path)
    assert material['campaign']==campaign and material['rst_sha256']==proof['rst_sha256']
    assert material['contact_verdict_sha256']==digest(proof_path)
    maps_path=base/'damage_footprint'/(case+'.json')
    verified(maps_path,proof['damage_footprint_sha256'])
    maps=read(maps_path)
    assert maps['rst_sha256']==proof['rst_sha256'] and maps['threshold']==proof['damage_reporting_threshold']
    history=material['history']
    sets=np.array([r['native_set'] for r in history])
    assert np.array_equal(np.repeat(sets,2),[r['native_set'] for r in contacts])
    endpoint=int(sets[-1])
    limits={k:r['native_set'] for k,r in material['first_reference_crossings'].items() if k.startswith('all_')}
    # The 0.05 mm screen belongs to the local rigid-hardware/PLA contact pairs.
    over=[r['native_set'] for r in contacts if r['max_closed_corner_penetration_mm']>.05]
    if over:
        limits['hardware_penetration_mm']=over[0]
    first_limit=min(limits.values(),default=endpoint+1)
    eligible=sets[sets<first_limit]
    damage=proof['damage_onset_bracket']
    onset=damage[-1]['native_set'] if damage else None
    mapped=maps['first_mapped_crossing']
    if mapped is not None:
        # The field maps start at lateral pull; the inventory also covers tightening.
        assert onset is not None and onset<=mapped['first_mapped_state']['native_set']
    inventory=ROOT/'.runtime/archive'/campaign/case/'set_inventory.csv'
    verified(inventory,maps['inventory_sha256'])
    native=table(inventory)
    assert np.array_equal(native['set'],sets) and np.allclose(native['ux_mm'],[r['travel_mm'] for r in history])
    before=None
    if len(eligible):
        row=native[native['set']==eligible[-1]][0]
        before=dict(native_set=int(row['set']),travel_mm=float(row['ux_mm']),cell_force_N=float(row['fx_N']),
                    section_damage=float(row['damage']))
    if onset is None:
        location='No threshold crossing in the converged history.'
    elif not limits:
        location='The nickel threshold was crossed within the recorded PLA and contact screens.'
    elif onset==first_limit:
        location='Nickel threshold and first PLA or contact limit occurred in the same saved increment.'
    elif onset<first_limit:
        location='Nickel threshold preceded the first PLA or contact limit in the saved history.'
    else:
        location='Nickel threshold occurred after the first PLA or contact limit.'
    write_json(base/'pulls'/(case+'_damage_scope.json'),dict(case=case,campaign=campaign,
        rst_sha256=proof['rst_sha256'],fixture_audit_sha256=digest(proof_path),material_audit_sha256=digest(material_path),
        section_map_sha256=digest(maps_path),contact_table_sha256=digest(base/'pulls'/(case+'_contact.csv')),
        nickel_reporting_threshold=maps['threshold'],nickel_bracket=damage,first_criterion_sets=limits,
        last_station_before_limits=before,interpretation=location,
        scope=('Native converged states of the 1.250 mm snug lateral fixture' if case.startswith('snug125_') else
               'Native converged states of the raised lateral fixture')+' with the assumed nickel law. A section damage '
              'threshold marks onset within the model. Rupture and crack propagation require independent evidence.'))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('case');verify(parser.parse_args().case)

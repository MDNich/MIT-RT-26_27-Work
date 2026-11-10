"""Compare a closed directional pull with the matching bare fixture at equal force and equal travel."""
import argparse
import csv
import re

import numpy as np

from audit_local import ROOT, read, table
from compare_pull import series
from film_identity import digest, verified, write_json
from stage_snug_fit import AUDIT


def first_bracket(rows, quantity, target, sign):
    """Return saved signed states on the first crossing, with interpolation confined to the interval."""
    values=np.array([sign*r[quantity] for r in rows])
    indices=np.flatnonzero(values>=sign*target-1e-9)
    if not len(indices):
        return None
    upper=int(indices[0])
    exact=bool(abs(values[upper]-sign*target)<1e-9)
    if upper==0 and not exact:
        return None
    lower=upper if exact else upper-1
    alpha=0. if exact else (sign*target-values[lower])/(values[upper]-values[lower])
    assert 0<=alpha<=1
    x,y=rows[lower],rows[upper]
    return dict(native_sets=[x['set'],y['set']],native_travel_mm=[x['ux_mm'],y['ux_mm']],
                native_force_N=[x['cell_force_N'],y['cell_force_N']],exact_saved_station=exact,
                travel_mm=(1-alpha)*x['ux_mm']+alpha*y['ux_mm'],
                cell_force_N=(1-alpha)*x['cell_force_N']+alpha*y['cell_force_N'])


def paired(case,bare,verdict):
    ref,base=series(bare)
    proof,rows=series(case,proof_path=verdict)
    assert proof['source']==ref['source'] and proof['campaign']==ref['campaign']
    sign=-1 if proof['source'].endswith('_minus') else 1
    assert np.all(np.diff([sign*r['ux_mm'] for r in rows])>0)
    assert np.isclose(base[-1]['ux_mm'],sign*.5,rtol=0,atol=1e-8)
    path=ROOT/'validation/pull_material'/(case+'.json')
    mat=read(path); assert mat['rst_sha256']==proof['rst_sha256'] and mat['contact_verdict_sha256']==digest(verdict)
    contact_file=ROOT/'validation/pulls'/(case+'_contact.csv')
    check=read(contact_file.with_suffix('.json'));assert check['rst_sha256']==proof['rst_sha256']
    with contact_file.open() as stream:
        both=list(csv.DictReader(stream))
    contacts={int(r['native_set']):r for r in both if int(r['pair'])==861}
    assert [(int(r['native_set']),int(r['pair'])) for r in both]==[(k,p) for k in contacts for p in (861,862)]
    assert np.isclose(max(float(r['max_closed_corner_penetration_mm']) for r in both),
                      check['max_closed_corner_penetration_mm'])
    penetration_limit=.05  # Same closed-corner comparison screen as the original bilateral studies.
    first_excess=next((r for r in both if float(r['max_closed_corner_penetration_mm'])>penetration_limit),None)
    assert len(contacts)==check['converged_states']==proof['states']
    material={r['native_set']:r for r in mat['history']}
    assert material.keys()==contacts.keys()
    limits=mat['reference_properties']
    all_limits={k:v for k,v in mat['first_reference_crossings'].items() if k.startswith('all_') and not k.startswith('all_four_')}
    stop=min((v['native_set'] for v in all_limits.values()),default=proof['states']+1)
    print_stop=stop
    if first_excess is not None:
        stop=min(stop,int(first_excess['native_set']))
    supported=[r for r in rows if r['set']<stop]
    first_contact=next((i for i,r in enumerate(rows) if int(contacts[r['set']]['closed_faces'])>0),None)
    record=dict(case=case,bare=bare,source=proof['source'],full_numerical_path=proof['full_requested_path'],
                fixture_sha256=digest(verdict),native_rst_sha256=proof['rst_sha256'],bare_rst_sha256=ref['rst_sha256'],
                print_material_sha256=digest(path),contact_csv_sha256=digest(contact_file),
                first_print_reference_crossings=all_limits,closed_corner_screen_mm=penetration_limit,
                first_contact_screen_exceeded=None if first_excess is None else
                    dict(native_set=int(first_excess['native_set']),pair=int(first_excess['pair']),
                         penetration_mm=float(first_excess['max_closed_corner_penetration_mm'])),
                last_converged_travel_mm=rows[-1]['ux_mm'],
                supported_pull_stations=len(supported),bare_endpoint_load_N=base[-1]['cell_force_N'],
                moving_cell_contact_bracket=None,equal_load=None,equal_travel=None,
                scope='First loading branch at matched displacement or matched bare terminal force. All reported '
                      'comparisons stop before the first printed-material or closed-corner penetration screen is exceeded. Screw beam stress '
                      'is given in MPa; the fitted screw grade and thread capacity have no established allowable.')
    if first_contact is not None:
        pair=rows[max(0,first_contact-1):first_contact+1]
        record['moving_cell_contact_bracket']=dict(native_sets=[r['set'] for r in pair],travel_mm=[r['ux_mm'] for r in pair],
                                                  within_print_screen=pair[-1]['set']<print_stop,within_both_screens=pair[-1]['set']<stop)
    if supported:
        load=first_bracket(supported,'cell_force_N',base[-1]['cell_force_N'],sign)
        if load is not None:
            record['equal_load']=dict(bare_travel_mm=base[-1]['ux_mm'],cased=load,
                                     reduction_in_absolute_travel_pct=100*(1-abs(load['travel_mm']/base[-1]['ux_mm'])))
        in_range=[r for r in supported if sign*r['ux_mm']<=sign*base[-1]['ux_mm']+1e-9]
        if in_range and sign*in_range[-1]['ux_mm']>0:
            last=in_range[-1];other=first_bracket(base,'ux_mm',last['ux_mm'],sign)
            assert other is not None
            m=material[last['set']]
            assert abs(m['travel_mm']-last['ux_mm'])<1e-7
            ratios={k:100*m['all_'+k]/val for k,val in limits.items()}
            assert max(ratios.values())<100
            record['equal_travel']=dict(cased=last,bare=other,cased_over_bare_force=last['cell_force_N']/other['cell_force_N'],
                        printed_coupon_percent=ratios,peak_screw_fibre_tensions_MPa=m['four_screws']['peak_fiber_tension_MPa'],
                        max_loaded_penetration_mm=float(contacts[last['set']]['max_closed_corner_penetration_mm']))
    return record


def initial_gaps(listing):
    blocks=re.split(r'Rigid-deformable contact pair identified by real constant set\s+(\d+)\b',listing)
    rows={}
    for number,text in zip(blocks[1::2],blocks[2::2],strict=True):
        if number not in ('861','862') or number in rows:
            continue
        match=re.search(r'(Min\.\s+Initial gap|Max\.\s+Initial penetration)\s+([+\-0-9.EeDd]+) was detected between contact element\s+'
                        r'(\d+) and target element\s+(\d+)',text)
        if match:
            kind='gap' if 'gap' in match[1] else 'penetration'
            value=abs(float(match[2].replace('D','E')))
            rows[number]=dict(gap_mm=value if kind=='gap' else -value,classification=kind,
                              contact_element=int(match[3]),target_element=int(match[4]))
    assert rows.keys()=={'861','862'}
    return rows


def registered_gaps(folder,hashes,spec,case_mesh):
    from ansys.mapdl import reader
    from stage_snug_fit import MESH,STEP_HASH
    shape=read(AUDIT/f'mesh_{case_mesh}.json');assert shape['step_sha256']==STEP_HASH
    cad_file=ROOT/'validation/alternate_case_fit.json'
    cad=read(cad_file)['Balius_native']['shortest_gaps_mm']['1.25']
    verified(folder/'solve.out',hashes['solve.out'])
    rows=initial_gaps((folder/'solve.out').read_text(errors='replace'))
    verified(folder/'pull.rst',hashes['pull.rst'])
    raw=reader.read_binary(str(folder/'pull.rst'))
    where={int(e):i for i,e in enumerate(raw.mesh.enum)}
    skin_path=MESH/'fixture_targets_0005.npz';verified(skin_path,spec['target_sha256'])
    mesh_path=MESH/f'case_{case_mesh}.npz';verified(mesh_path,spec['mesh_sha256'])
    with np.load(skin_path) as skin,np.load(mesh_path) as mesh:
        for pair,row in rows.items():
            target=raw.mesh.elem[where[row['target_element']]]
            face=raw.mesh.elem[where[row['contact_element']]]
            assert target[1]==861 and face[1]==862 and target[2]==face[2]==int(pair)
            target_offset=1600000 if pair=='861' else 1800000
            tri=np.sort(target[10:13]-target_offset)
            bodies=[4] if pair=='861' else [15,19,1,6,9,10,11,20]
            owner,=[b for b in bodies if np.any(np.all(np.sort(skin[str(b)],axis=1)==tri,axis=1))]
            nodes=face[10:18]
            assert len(nodes)==8 and nodes[2]==nodes[3]==nodes[6]
            key=np.sort(nodes[[0,1,2,4,5,7]]-2100001)
            case_face,=[int(f) for f in mesh if f.isdigit() and np.any(np.all(np.sort(mesh[f],axis=1)==key,axis=1))]
            reference=cad.get(str(owner))
            row.update(target_body=owner,case_STEP_face=case_face,CAD_gap_mm=reference,
                       native_minus_CAD_um=None if reference is None else 1000*(row['gap_mm']-reference))
    return dict(pairs=rows,native_listing_sha256=hashes['solve.out'],CAD_fit_sha256=digest(cad_file))


def reconcile_checkpoint(checkpoint, verdict, ledger):
    """Compare every checkpoint station with the closed native POST1 and material readbacks."""
    item=read(checkpoint);proof=read(verdict);case=proof['case'];campaign=proof['campaign']
    sha={f['name']:f['sha256'] for f in ledger['files']}
    assert item['case']==case and item['campaign']==campaign and not item['completed']
    assert item['input_sha256']==sha['model.inp'] and sha['pull.rst']==proof['rst_sha256']
    archive=ROOT/'.runtime/archive'/campaign/case
    verified(archive/'case_pairs.csv',sha['case_pairs.csv'])
    pairs=table(archive/'case_pairs.csv')
    fx=table(ROOT/'.runtime/post'/campaign/case/'whole_fixture_balance.csv')
    mat=read(ROOT/'validation/pull_material'/(case+'.json'))
    assert mat['rst_sha256']==proof['rst_sha256'] and mat['contact_verdict_sha256']==digest(verdict)
    limit=mat['reference_properties'];history=mat['history']
    contact_file=ROOT/'validation/pulls'/(case+'_contact.csv')
    contact_record=read(contact_file.with_suffix('.json'))
    assert contact_record['rst_sha256']==proof['rst_sha256']
    fields=('native_set','pair','closed_faces','closed_corner_records','max_closed_corner_penetration_mm')
    contacts=np.genfromtxt(contact_file,delimiter=',',names=True,usecols=fields)
    assert len(contacts)==len(pairs) and np.isfinite(contacts.view(float)).all()
    n=item['converged_sets']
    assert len(item['states'])==n and len(fx)>=n
    for i,r in enumerate(item['states']):
        k=r['native_set'];br=fx[i];mr=history[i]
        assert k==int(br['native_set'])==mr['native_set']==i+1
        assert (r['loadstep'],r['substep'])==(br['loadstep'],br['substep'])
        assert abs(r['travel_mm']-br['ux_mm'])<1e-7
        forces=[r['cell_force_N'],r['screw_support_resistance_N'],r['neighbor_resistance_N'],r['nickel_clamp_resistance_N']]
        closed=[br['cell_fx_N'],-br['screw_support_N_x'],-br['neighbor_support_N_x'],
                br['cell_fx_N']+br['screw_support_N_x']+br['neighbor_support_N_x']-br['force_N_x']]
        np.testing.assert_allclose(forces,closed,atol=1e-5,rtol=2e-6)
        assert abs(r['screw_peak_fibre_MPa']-max(mr['four_screws']['peak_fiber_tension_MPa']))<1e-6
        for field,v in r['printed_coupon_percent'].items():
            assert abs(v-100*mr['all_'+field]/limit[field])<1e-6
        for pair,c in r['both_contact_pairs'].items():
            rid=int(pair)
            rr,=pairs[(pairs['set']==k)&(pairs['pair']==rid)]
            cc,=contacts[(contacts['native_set']==k)&(contacts['pair']==rid)]
            assert c['closed_faces']==rr['closed']==cc['closed_faces'] and c['loaded_corners']==cc['closed_corner_records']
            assert abs(c['max_loaded_penetration_mm']-cc['max_closed_corner_penetration_mm'])<1e-7
            np.testing.assert_allclose(c['force_N'],[rr[a+'_N'] for a in ('fx','fy','fz')],atol=1e-5,rtol=2e-6)
    receipt=dict(checkpoint=checkpoint.name,checkpoint_sha256=digest(checkpoint),agreed_native_sets=n,
                 stationary_rst_sha256=item['rst_sha256'],closed_rst_sha256=sha['pull.rst'])
    strain_file=checkpoint.with_name(checkpoint.stem.removesuffix('_checkpoint')+'_nickel_strain.json')
    if strain_file.is_file():
        strain=read(strain_file)
        assert strain['checkpoint_sha256']==receipt['checkpoint_sha256'] and strain['case']==case
        verified(archive/'history.csv',sha['history.csv'])
        rows=table(archive/'history.csv')[:n]
        assert np.array_equal(rows['set'],[r['native_set'] for r in strain['states']])
        np.testing.assert_allclose(rows['max_eppl'],[r['peak'] for r in strain['states']],rtol=2e-7,atol=1e-8)
        receipt['nickel_strain_sha256']=digest(strain_file)
    return receipt


def run(case):
    suffix='_m3' if case.endswith('_m3') else '_m15'
    inputs=read(AUDIT/('local_inputs'+suffix+'.json'));spec=inputs[case]
    assert spec['source'] in ('lateral_friction_locked','lateral_friction_locked_minus')
    name=case+'.json'
    verdict,=[p for k in ('local','partial_local') if (p:=ROOT/'validation'/k/name).is_file()]
    record=paired(case,spec['bare_reference'],verdict)
    ledger=read(ROOT/'.runtime/receipts'/read(verdict)['campaign']/case/'archived.json')
    sha={r['name']:r['sha256'] for r in ledger['files']}
    assert sha['model.inp']==spec['input_sha256'] and sha['pull.rst']==record['native_rst_sha256']
    verified(ROOT/'.runtime/archive'/ledger['campaign']/case/'model.inp',spec['input_sha256'])
    record['initial_contact_search']=registered_gaps(ROOT/'.runtime/archive'/ledger['campaign']/case,sha,spec,
                                                   '3' if suffix=='_m3' else '1.5')
    record['case_mesh_sha256']=spec['mesh_sha256'];record['input_sha256']=spec['input_sha256']
    record['verified_checkpoints']=[reconcile_checkpoint(p,verdict,ledger)
                                    for p in sorted(AUDIT.glob(case+'_*_checkpoint.json'))]
    if suffix=='_m15':
        from snug_mount_reactions import archive as check_mounts
        record['mount_history_sha256']=digest(check_mounts(case,record,ROOT/'.runtime/archive'/ledger['campaign']/case,sha))
    write_json(AUDIT/(case+'_comparison.json'),record)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case')
    run(parser.parse_args().case)

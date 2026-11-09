"""Resolve fixture travel at the bare 8.542 N reference load on the nominal damage-law meshes."""
import argparse
import json

import numpy as np

from audit_local import ROOT, read, table
from compare_pull_laws import at_first_crossing
from film_identity import digest, verified, write_json
from stage_local_jobs import seal


OUT=ROOT/'validation/common_pull_resolution.json'
PARENTS=('bare_damage_cont_nominal','stand3_nylon_damage_cont_nominal_pin1','stand3_aluminium_damage_cont_nominal_pin1')


def stage():
    comparison=ROOT/'validation/pull_laws/stand3_nylon.json'
    reference=read(comparison)
    target=reference['bare_control_force_N']
    # The two nominal histories share five saved stations before the unresolved force crossing.
    grids=[]
    for case in PARENTS[:2]:
        evidence=reference['sources'][case]
        p=ROOT/'.runtime/archive'/evidence['campaign']/case/'set_inventory.csv'
        verified(p,evidence['native_history_sha256'])
        rows=table(p)
        bracket=reference['curves'][case]['at_bare_control_force']['bracket']
        assert bracket[0]['force_N']<target<bracket[1]['force_N']
        grids.append(rows['ux_mm'][(rows['loadstep']>=3)&(rows['set']<=bracket[1]['native_set'])])
    grid=grids[0]
    assert np.array_equal(grid,grids[1]) and np.array_equal(grid,[.025,.05,.0875,.1375,.1875,.21875])
    # Keep the parent loading sequence up to the observed lower bracket. Only the last
    # interval is finely divided, and the existing completed-load-step checks are retained.
    refined='\n'.join(['*DIM,PBTARG,ARRAY,6',*[f'PBTARG({i})={v:.9g}' for i,v in enumerate(grid,1)],
                      '*DO,JJ,1,6',' TIME,2+PBTARG(JJ)',' *IF,JJ,LT,6,THEN','  NSUBST,1,16,1',
                      ' *ELSE','  NSUBST,64,256,64',' *ENDIF',' D,2481,UX,PBTARG(JJ)'])
    original='*DO,JJ,1,32\n TIME,2+JJ*0.25\n NSUBST,10,2000,5\n D,2481,UX,0.25*JJ'
    cases={}
    for parent in PARENTS:
        reg=read(ROOT/'validation'/('local_jobs.json' if parent.startswith('bare_') else 'local_contact_retries.json'))[parent]
        inputs=ROOT/'.runtime/inputs'/parent
        verified(inputs/'local_job.json',reg['spec_sha256'])
        spec=read(inputs/'local_job.json')
        assert spec['source']=='damage_cont_nominal' and spec['case']==parent
        for name,sha in spec['files'].items():
            verified(inputs/name,sha)
        deck=(inputs/'model.inp').read_bytes()
        sep=b'\r\n' if b'\r\n' in deck else b'\n'
        old=original.encode().replace(b'\n',sep);new=refined.encode().replace(b'\n',sep)
        assert deck.count(old)==1 and new not in deck
        case=parent+'_load8ref1';dest=inputs.with_name(case);dest.mkdir(exist_ok=True)
        candidate=deck.replace(old,new);assert candidate.replace(new,old)==deck
        files={'model.inp':seal(dest/'model.inp',candidate)}
        for name in ('moving.inp','local_post.inp'):
            files[name]=seal(dest/name,(inputs/name).read_bytes())
        spec.update(case=case,files=files,common_load_parent=parent,
                    displacement_mm=float(grid[-1]),end_time=2+float(grid[-1]))
        spec_hash=seal(dest/'local_job.json',(json.dumps(spec,indent=2)+'\n').encode())
        cases[case]=dict(parent=parent,parent_input_sha256=reg['input_sha256'],parent_spec_sha256=reg['spec_sha256'],
                         input_sha256=files['model.inp'],spec_sha256=spec_hash,reference_sha256=digest(comparison),
                         target_force_N=target,pull_stations_mm=grid.tolist(),maximum_refined_step_mm=(grid[-1]-grid[-2])/64)
    write_json(OUT,cases)


def check(case,campaign):
    info=read(OUT)[case];parent=info['parent']
    def history(name):
        folder=ROOT/'.runtime/archive'/campaign/name
        ledger=read(ROOT/'.runtime/receipts'/campaign/name/'archived.json')
        assert ledger['case']==name and ledger['campaign']==campaign
        path=folder/'set_inventory.csv'
        verified(path,next(f['sha256'] for f in ledger['files'] if f['name']==path.name))
        return table(path),digest(path)
    fine,fine_sha=history(case);coarse,coarse_sha=history(parent)
    assert abs(fine['ux_mm'][-1]-info['pull_stations_mm'][-1])<1e-8
    # Compare the overlapping original equilibria through the lower bracket, including the lock.
    start=info['pull_stations_mm'][-2]
    prefix=coarse[coarse['ux_mm']<=start+1e-9]
    indices=np.searchsorted(fine['time'],prefix['time']-1e-9)
    assert max(indices)<len(fine)
    same=np.isclose(prefix['time'],fine['time'][indices],rtol=0,atol=1e-8)
    # Different screw properties can cause different automatic subdivisions. Compare
    # every shared state, including the complete preload/lock sequence and early pull.
    assert np.all(same[prefix['loadstep']<=2]) and np.count_nonzero(same & (prefix['loadstep']>=3))>=2
    original_prefix_states=len(prefix)
    prefix_fine=fine[indices[same]]
    prefix=prefix[same]
    err=float(abs(prefix_fine['fx_N']-prefix['fx_N']).max())
    scale=np.maximum(1,abs(prefix['fx_N']))
    assert np.max(abs(prefix_fine['fx_N']-prefix['fx_N'])/scale)<.001
    interval=fine[fine['ux_mm']>=start-1e-9]
    assert np.all(np.diff(interval['ux_mm'])>0)
    assert np.max(np.diff(interval['ux_mm']))<=info['maximum_refined_step_mm']+1e-8
    # Use the same native binary reactions and verified case material/contact range as the main comparison.
    balance=table(ROOT/'.runtime/post'/campaign/case/'whole_fixture_balance.csv')
    assert np.array_equal(balance['native_set'],fine['set']) and np.allclose(balance['cell_fx_N'],fine['fx_N'],rtol=1e-7,atol=1e-6)
    if not case.startswith('bare_'):
        scope=read(ROOT/'validation/pulls'/(case+'_damage_scope.json'))
        assert scope['last_station_before_limits']['native_set']==int(fine['set'][-1]) and not scope['first_criterion_sets']
    target=at_first_crossing(balance[balance['loadstep']>=3],'cell_fx_N',info['target_force_N'])
    assert target is not None and target['bracket'][0]['travel_mm']>=start-1e-8
    write_json(ROOT/'validation/refined_pull_force'/(case+'.json'),dict(case=case,parent=parent,campaign=campaign,
               original_inventory_sha256=coarse_sha,refined_inventory_sha256=fine_sha,setup_sha256=digest(OUT),
               target_force_N=info['target_force_N'],original_prefix_states=original_prefix_states,matched_prefix_states=len(prefix),max_prefix_force_difference_N=err,
               max_refined_travel_increment_mm=float(np.diff(interval['ux_mm']).max()),at_reference_force=target))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case',nargs='?');parser.add_argument('--campaign',default='nov08_01')
    args=parser.parse_args()
    if args.case:check(args.case,args.campaign)
    else:stage()

"""Localize the fixed-hardware reaction with the loaded contact facets and each rigid STEP body's target skin."""
import argparse
from pathlib import Path
import numpy as np
from ansys.mapdl import reader
from audit_local import ROOT,read,table
from early_cell_clearance import bezier
from film_cell_contact import candidate_pairs
from film_identity import digest,verified,write_json
from local_equilibrium import positions,NEIGHBOR_PILOT
from stage_snug_fit import AUDIT,INPUTS,MESH
from tab_seating import read_point_file


def classify(folder,case,rst_sha,spec,states,out):
    target=MESH/'fixture_targets_0005.npz'
    verified(target,spec['target_sha256']);verified(folder/'pull.rst',rst_sha)
    job_path=INPUTS/case/'local_job.json';verified(job_path,spec['spec_sha256'])
    job=read(job_path);deck=INPUTS/case/'model.inp'
    verified(deck,spec['input_sha256'])
    radius=job['absolute_search_mm']
    assert radius==1. and 'RMODIF,862,6,-1\n' in deck.read_text()
    raw=reader.read_binary(folder/'pull.rst')
    elements=[e for e in raw.mesh.elem if e[1]==862 and e[2]==862]
    elements.sort(key=lambda e:e[8])
    ids=np.array([e[8] for e in elements]);faces=np.stack([e[10:18] for e in elements])
    assert np.array_equal(faces[:,2],faces[:,3]) and np.array_equal(faces[:,2],faces[:,6])
    faces=faces[:,[0,1,2,4,5,7]]
    rigid=[e[10:14] for e in raw.mesh.elem if e[1]==861 and e[2]==862]
    assert sum(e[0]==NEIGHBOR_PILOT and e[2]==0 for e in rigid)==1
    native_tri=np.stack([e[:3] for e in rigid if e[2]>0])
    bodies=(15,19,1,6,9,10,11,20)
    with np.load(target) as skin:
        original=np.vstack([skin[str(b)]+1800000 for b in bodies])
        as_set=lambda a:{tuple(x) for x in np.sort(a,axis=1)}
        assert len(native_tri)==len(original) and as_set(original)==as_set(native_tri)
        boxes={}
        for b in bodies:
            p=raw.mesh.nodes[positions(raw.mesh.nnum,(skin[str(b)]+1800000).ravel())].reshape(-1,3,3)
            assert np.max(abs(p-skin['points'][skin[str(b)]]))<1e-6
            boxes[b]=(p.min(axis=1),p.max(axis=1))
    live=[]
    for row in states:
        if not row['within_screens']:break
        k=row['native_set'];enum,values,_=raw.element_solution_data(k-1,'EMN')
        idx=positions(enum,ids)
        exists=np.array([values[i] is not None and len(values[i])>0 for i in idx])
        if not exists.any():continue
        native=np.stack([values[i] for i in idx[exists]])
        force=native[:,42:45];moving=np.any(native[:,:4]>=2,axis=1)|(native[:,40]>=2)
        assert np.allclose(force[~moving],0.,atol=1e-8)
        ref=row['both_contact_pairs']['862']
        assert (native[:,40]>=2).sum()==ref['closed_faces']
        assert np.allclose(force.sum(axis=0,dtype=float),ref['force_N'],atol=1e-5,rtol=1e-6)
        if moving.any():live.append((row,faces[exists][moving],force[moving].astype(float)))
    if not live:
        return []
    nodes=np.unique(np.r_[NEIGHBOR_PILOT,np.concatenate([f.ravel() for _,f,_ in live])])
    sets=[r['native_set'] for r,_,_ in live]
    u,_=read_point_file(folder/'pull.rst',out,rst_sha,sets,nodes.tolist())
    assert np.max(abs(u[:,positions(nodes,[NEIGHBOR_PILOT])]))<1e-9
    records=[]
    for (row,f,forces),field in zip(live,u,strict=True):
        points=raw.mesh.nodes[positions(raw.mesh.nnum,f.ravel())]+field[positions(nodes,f.ravel())]
        controls=bezier(points.reshape(-1,6,3))
        box=(controls.min(axis=1)-radius-1e-6,controls.max(axis=1)+radius+1e-6)
        owners=[[] for _ in f]
        for b,limits in boxes.items():
            hits,_=candidate_pairs(box,limits)
            for i in np.unique(hits):owners[i].append(b)
        assert all(owners)
        groups={}
        for choices,v in zip(owners,forces,strict=True):
            key=','.join(str(i) for i in sorted(choices))
            if key not in groups:groups[key]=dict(faces=0,force_N=np.zeros(3))
            groups[key]['faces']+=1;groups[key]['force_N']+=v
        for group in groups.values():group['force_N']=group['force_N'].tolist()
        total=sum(g['force_N'][0] for g in groups.values())
        assert abs(total-row['neighbor_resistance_N'])<.01
        records.append(dict(native_set=row['native_set'],travel_mm=row['travel_mm'],cell_force_N=row['cell_force_N'],
                            fixed_resistance_N=total,possible_target_bodies=groups))
        print(row['native_set'],{k:round(v['force_N'][0],2) for k,v in groups.items()},flush=True)
    return records


def write_result(path,case,source_key,source_sha,spec,out,records,*,last_comparison_set=None):
    result=dict(case=case,skin_sha256=spec['target_sha256'],fixed_body_numbers=[15,19,1,6,9,10,11,20],
                search_radius_mm=1.,loaded_states=records,
                scope='Each target triangle has its exact native vertices. The deformed quadratic contact-face hull '
                      'bounds are expanded by the full 1 mm native search radius in each coordinate. A unique candidate '
                      'body establishes attribution. Ambiguous facet forces are retained as a group.')
    result[source_key]=source_sha
    if last_comparison_set is not None:result['last_comparison_set']=last_comparison_set
    if records:result['DPF_displacements_sha256']=digest(out/'displacements.bin')
    write_json(path,result)
    return path


def check(folder):
    cap=read(folder/'capture.json');case=cap['case']
    source=AUDIT/f'{case}_{folder.name}_checkpoint.json';checkpoint=read(source)
    assert checkpoint['rst_sha256']==cap['sha256']
    spec=read(AUDIT/'local_inputs_m15.json')[case];out=folder/'dpf_fixed_faces'
    rows=classify(folder,case,cap['sha256'],spec,checkpoint['states'],out)
    return write_result(AUDIT/f'{case}_{folder.name}_fixed_targets.json',case,'checkpoint_sha256',digest(source),spec,out,rows)


def archive(case,comparison,folder,sha):
    spec=read(AUDIT/'local_inputs_m15.json')[case]
    assert spec['input_sha256']==sha['model.inp'] and sha['pull.rst']==comparison['native_rst_sha256']
    post=ROOT/'.runtime/post'/folder.parent.name/case
    verified(folder/'case_pairs.csv',sha['case_pairs.csv'])
    pairs=table(folder/'case_pairs.csv');balance=table(post/'whole_fixture_balance.csv')
    fixed=pairs[pairs['pair']==862]
    assert np.array_equal(fixed['set'],balance['native_set'])
    end=comparison['equal_travel'];supported=end['cased']['set'] if end else 0
    last=comparison.get('parent_screen_last_set',supported)
    rows=[dict(native_set=int(b['native_set']),within_screens=True,travel_mm=b['ux_mm'],cell_force_N=b['cell_fx_N'],
               neighbor_resistance_N=-b['neighbor_support_N_x'],both_contact_pairs={'862':dict(
               closed_faces=f['closed'],force_N=[f[k+'_N'] for k in ('fx','fy','fz')])})
          for b,f in zip(balance,fixed,strict=True) if b['native_set']<=last]
    out=post/'dpf_fixed_faces'
    records=classify(folder,case,sha['pull.rst'],spec,rows,out) if rows else []
    keyed={r['native_set']:r['possible_target_bodies'] for r in records}
    for path in sorted(AUDIT.glob(case+'_ls*_fixed_targets.json')):
        snap=read(path)
        assert snap['checkpoint_sha256'] in {c['checkpoint_sha256'] for c in comparison['verified_checkpoints']}
        for row in snap['loaded_states']:
            before=row['possible_target_bodies'];after=keyed[row['native_set']]
            assert before.keys()==after.keys()
            for k,v in before.items():
                assert v['faces']==after[k]['faces']
                np.testing.assert_allclose(v['force_N'],after[k]['force_N'],atol=1e-5,rtol=1e-6)
    return write_result(AUDIT/f'{case}_fixed_target_history.json',case,'closed_rst_sha256',sha['pull.rst'],spec,out,records,last_comparison_set=supported)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);check(p.parse_args().folder.resolve())

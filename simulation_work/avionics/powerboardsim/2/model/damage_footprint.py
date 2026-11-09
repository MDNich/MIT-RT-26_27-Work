"""Verify per-element section damage exports and locate the affected nickel shell elements."""
import argparse
import hashlib
from pathlib import Path

import numpy as np
from ansys.mapdl import reader
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json


def shell_components(corners,node_count):
    edges=np.stack((corners.ravel(),np.roll(corners,-1,axis=1).ravel()))
    graph=coo_matrix((np.ones(edges.shape[1]),edges),shape=(node_count,node_count))
    return connected_components(graph,directed=False)


def strip_terminals(ids,node_strip,strips,mesh):
    terminals=[]
    for strip in strips:
        groups=[]
        for key in ('attachment','clamp'):
            picked=np.searchsorted(ids,mesh[key])
            assert np.array_equal(ids[picked],mesh[key])
            group=picked[node_strip[picked]==strip]
            assert len(group)
            groups.append(group)
        assert not np.intersect1d(*groups).size
        terminals.append(groups)
    return terminals


def surviving_paths(corners,node_count,terminals,removed):
    _,labels=shell_components(corners[~removed],node_count)
    return [bool(np.intersect1d(labels[attachment],labels[clamp]).size) for attachment,clamp in terminals]


def check(folder,mesh_file,rst_sha):
    verified(folder/'tear.rst',rst_sha)
    mesh=read(mesh_file)
    rst=reader.read_binary(str(folder/'tear.rst'))
    elements=np.arange(1,len(mesh['elements'])+1)
    corners=np.asarray(mesh['elements'])
    idx=np.argsort(rst.mesh.enum)
    ix=idx[np.searchsorted(rst.mesh.enum[idx],elements)]
    assert np.array_equal(rst.mesh.enum[ix],elements)
    native=rst.mesh.elem
    assert np.array_equal(corners,np.stack([native[i][10:] for i in ix]))
    ids,inv=np.unique(corners,return_inverse=True)
    idx=np.searchsorted(rst.mesh.nnum,ids);assert np.array_equal(rst.mesh.nnum[idx],ids)
    coords=rst.mesh.nodes[idx]
    assert np.allclose(coords,[mesh['nodes'][str(n)] for n in ids],rtol=0,atol=1e-7)
    xyz=coords[inv.reshape(corners.shape)]
    centres=xyz.mean(1)
    def triangle(a,b,c):return .5*np.linalg.norm(np.cross(b-a,c-a),axis=1)
    area=triangle(xyz[:,0],xyz[:,1],xyz[:,2])+triangle(xyz[:,0],xyz[:,2],xyz[:,3])
    reverse=triangle(xyz[:,0],xyz[:,1],xyz[:,3])+triangle(xyz[:,1],xyz[:,2],xyz[:,3])
    assert np.allclose(area,reverse,rtol=1e-5,atol=1e-8)
    assert np.isclose(area.sum(),mesh['area'],rtol=1e-6) and area.min()>0
    # Identify the two strips by mesh connectivity, independent of shell numbering.
    compact=inv.reshape(corners.shape)
    count,node_strip=shell_components(compact,len(ids))
    assert count==2
    per_corner_strip=node_strip[compact]
    assert np.all(per_corner_strip==per_corner_strip[:,:1])
    component=per_corner_strip[:,0]
    strips=sorted(range(count),key=lambda i:centres[component==i,1].mean())
    terminals=strip_terminals(ids,node_strip,strips,mesh)
    previous_removal=np.zeros(len(elements),dtype=bool)
    connected=surviving_paths(compact,len(ids),terminals,previous_removal)
    assert connected==[True,True]
    connectivity=[]
    inventory=table(folder/'set_inventory.csv');history=table(folder/'history.csv')
    ls=rst._resultheader['ls_table']
    valid=np.flatnonzero(ls[:,1]!=999999)
    assert np.array_equal(inventory['set'],valid+1)
    assert np.array_equal(inventory['loadstep'],ls[valid,0]) and np.array_equal(inventory['substep'],ls[valid,1])
    assert np.allclose(inventory['time'],rst.time_values[valid],rtol=0,atol=1e-7)
    threshold=1e-4
    onset=None;last=None;maximum=0.
    hashes=hashlib.sha256()
    paths=[];previous=None
    assert np.array_equal(history['step'],np.arange(1,len(history)+1)) and np.all(np.diff(history['time'])>0)
    for row in history:
        (match,)=inventory[np.isclose(inventory['time'],row['time'],atol=1e-7,rtol=0)]
        jj=int(row['step']);path=folder/f'damage_{jj}.csv'
        hashes.update((path.name+' '+digest(path)+'\n').encode())
        a=table(path)
        assert np.array_equal(a['element'],elements)
        assert np.allclose(a['z_mm'],centres[:,2],rtol=0,atol=1e-5)
        fields=np.column_stack([a[n] for n in ('damage_top','damage_mid','damage_bot')])
        assert np.allclose(fields.max(0),[row[n] for n in ('dtop','dmid','dbot')],atol=1e-8)
        assert np.isclose(fields.max(),match['damage'],atol=1e-8) and fields.max()<=1.00001
        hits=fields>threshold
        active=hits.any(1)
        state=dict(native_set=int(match['set']),time=float(row['time']),travel_mm=float(row['ux_mm']),force_N=float(row['fx_N']))
        degraded=fields>=.99
        removed=degraded.all(axis=1)
        if not np.array_equal(removed,previous_removal):
            connected=surviving_paths(compact,len(ids),terminals,removed)
            previous_removal=removed
        connectivity.append(dict(**state,pull_step=jj,any_section_d99=int(degraded.any(axis=1).sum()),
                                 all_sections_d99=int(removed.sum()),connected_low_high_Y=connected))
        if not active.any():
            previous=state
            continue
        maximum=max(maximum,float(fields.max()))
        def mask_summary(mask):
            ind=np.flatnonzero(mask)
            return dict(elements=int(len(ind)),reference_shell_area_mm2=float(area[ind].sum()),
                        regions=sorted(set(mesh['region'][i] for i in ind)))
        count_by_strip=[mask_summary(active&(component==i)) for i in strips]
        sections={key:mask_summary(hits[:,j]) for j,key in enumerate(('top','middle','bottom'))}
        peak=np.unravel_index(np.argmax(fields),fields.shape)
        details=dict(**state,low_high_Y_strips=count_by_strip,sections=sections,
                     peak_element=int(elements[peak[0]]),peak_face=['top','middle','bottom'][peak[1]],
                     peak_value=float(fields[peak]),original_peak_centroid_mm=centres[peak[0]].tolist())
        if onset is None:onset=dict(previous_pull_state=previous,first_mapped_state=details)
        last=details
        paths.append(dict(native_set=state['native_set'],elements=int(active.sum()),
                          reference_shell_area_mm2=float(area[active].sum()),peak_value=details['peak_value']))
        previous=state
    footprint=dict(rst_sha256=rst_sha,mesh_sha256=digest(mesh_file),history_sha256=digest(folder/'history.csv'),
        inventory_sha256=digest(folder/'set_inventory.csv'),per_state_field_hash_manifest_sha256=hashes.hexdigest(),
        pull_states=len(history),native_sets=len(valid),excluded_diagnostic_sets=len(ls)-len(valid),threshold=threshold,
        reference_area_both_strips_mm2=float(area.sum()),first_mapped_crossing=onset,last_mapped_state=last,
        mapped_exceedances=paths,largest_element_summary_damage=maximum,
        scope='Reference midsurface area of elements whose top, middle or bottom section summary exceeds the threshold. '
              'The maps cover saved lateral-pull states; installation is covered by the separate set inventory. '
              'Local corner damage, crack area and separation require separate evidence.')
    return footprint,connectivity


def path_summary(history):
    force=np.abs([r['force_N'] for r in history])
    peak=int(np.argmax(force))
    assert force[peak]>0
    changes=[]
    for row in history:
        if not changes or any(changes[-1][k]!=row[k] for k in ('any_section_d99','all_sections_d99','connected_low_high_Y')):
            changes.append(row)
    return dict(pull_states=len(history),peak_force_state=history[peak],last_state=history[-1],
                peak_is_endpoint=peak==len(history)-1,end_drop_from_peak_fraction=float(1-force[-1]/force[peak]),
                state_changes=changes,
                rule='In a copy of the shell connectivity, remove each element whose top, middle and bottom '
                     'section summaries all reach 0.99. Test each strip from its battery attachment to its clamp.',
                scope='Discrete diagnostic over saved lateral pull states. The solver retains all elements. '
                      'Section-average damage, model connectivity and a drop in total fixture reaction do not '
                      'individually establish physical fracture.')


def run(case,campaign,october=None):
    if october is not None:
        assert case=='october_nominal'
        source='damage_cont_nominal'
        spec=read(ROOT/'validation/local_inputs.json')[source]
        folder=october/spec['source_path']
        mesh=folder/'mesh.json';verified(mesh,spec['files']['mesh.json'])
        reference=read(ROOT/'validation/october_damage_reference.json')
        for name,sha in reference['source_hashes'].items():verified(folder/name,sha)
        sha=reference['source_hashes']['tear.rst']
    else:
        folder=ROOT/'.runtime/archive'/campaign/case
        receipt=ROOT/'.runtime/receipts'/campaign/case
        assert (receipt/'released.txt').is_file()
        ledger=read(receipt/'archived.json');assert ledger['case']==case and ledger['campaign']==campaign
        hashes={f['name']:f['sha256'] for f in ledger['files']}
        source=read(folder/'local_job.json')['source']
        assert source.startswith('damage_')
        mesh=ROOT/'.runtime/local_inputs'/source/'mesh.json'
        verified(mesh,read(ROOT/'validation/local_inputs.json')[source]['files']['mesh.json'])
        for name,identity in hashes.items():
            if name in ['local_job.json','set_inventory.csv','history.csv'] or name.startswith('damage_'):
                verified(folder/name,identity)
        required={f'damage_{int(i)}.csv' for i in table(folder/'history.csv')['step']}
        assert required.issubset(hashes)
        sha=hashes['tear.rst']
    data,history=check(folder,mesh,sha)
    data.update(case=case,campaign=campaign if october is None else 'October source')
    output=ROOT/'validation/damage_footprint'/(case+'.json')
    shape=path_summary(history)
    if october is not None:
        prior_file=folder/'path_assessment.json'
        prior=read(prior_file)
        assert prior['case']=='cont_nominal'
        for old,new in zip(prior['states'],history,strict=True):
            assert old['step']==new['pull_step'] and np.isclose(old['ux_mm'],new['travel_mm'])
            assert np.isclose(old['force_N'],abs(new['force_N']))
            assert old['elements_any_sample_d99']==new['any_section_d99']
            assert old['elements_all_three_samples_d99']==new['all_sections_d99']
            assert old['path_from_battery_to_clamp_after_virtual_removal']==new['connected_low_high_Y']
        shape['october_path_assessment_sha256']=digest(prior_file)
    write_json(output,data)
    shape.update(case=case,campaign=data['campaign'],footprint_sha256=digest(output),rst_sha256=sha)
    write_json(ROOT/'validation/damage_paths'/(case+'.json'),shape)
    print(case,data['pull_states'],data['last_mapped_state'],flush=True)
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('case')
    p.add_argument('--campaign',default='nov08_01');p.add_argument('--october-archive',type=Path)
    a=p.parse_args();run(a.case,a.campaign,a.october_archive)

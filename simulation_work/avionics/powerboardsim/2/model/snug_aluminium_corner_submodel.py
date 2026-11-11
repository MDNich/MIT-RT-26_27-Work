"""Refine two free PLA corners using the existing audited aluminium displacement fields."""
import fcntl
import os
import shutil

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT, read
from case_stress import corners
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_mount_reactions import ring_nodes
from snug_tab_crossing import local_points, native_geometry
from snug_tab_submodel import compute, material, native_average
from stage_snug_fit import AUDIT, INPUTS, MESH, STEP, STEP_HASH

CASE='snug125_aluminium_lateral_friction_locked_pin1_m15'
STAMP='ls3_ss15'
OFFSET=2100001
WORK=ROOT/'.runtime/qa/snug125/aluminium-corner-submodel'
OUTPUT=AUDIT/'aluminium_forward_corner_submodel.json'


def setup(node):
    record=AUDIT/f'{CASE}_{STAMP}_checkpoint.json';proof=read(record)
    energy_path=AUDIT/f'{CASE}_{STAMP}_energy.json';energy=read(energy_path)
    assert energy['checkpoint_sha256']==digest(record)
    assert proof['case']==CASE and proof['converged_sets']==24 and proof['first_excluded_set'] is None
    folder=ROOT/'.runtime/qa/snug125/directional-readback'/CASE/STAMP
    path=folder/'pull.rst';verified(path,proof['rst_sha256']);raw=reader.read_binary(path)
    spec=read(AUDIT/'local_inputs_m15.json')[CASE]
    assert spec['input_sha256']==proof['input_sha256']
    verified(STEP,STEP_HASH)
    meshfile=MESH/'case_1.5.npz';verified(meshfile,spec['mesh_sha256'])
    deck=INPUTS/CASE/'model.inp';verified(deck,spec['input_sha256'])
    rules=deck.read_text();rings,_=ring_nodes(rules)
    with np.load(meshfile) as m:
        native_geometry(raw,m,rules)
        x=local_points(m['points']);t=m['tets'][:,[0,1,2,3,4,5,6,7,9,8]]
        skin={tuple(row) for row in np.sort(np.vstack([m[k][:,:3] for k in m.files if k.isdigit()]),axis=1)}
    root=node-OFFSET
    distance=np.linalg.norm(x[t[:,:4]].mean(1)-x[root],axis=1)
    ids=np.unique(t[distance<3.75])+OFFSET
    sets=list(range(9,25));fields=[];field_hashes=[]
    out=ROOT/'.runtime/post/nov08_01'/CASE/'pull_work'/proof['rst_sha256'][:16]/'sets_9_24/U'
    request=read(out/'request.json')
    assert request['source_sha256']==proof['rst_sha256'] and request['sets']==sets and request['unit']=='mm'
    by_set={r['native_set']:r for r in energy['cased']['history']}
    for k in sets:
        stem=out/f'set_{k:04d}'
        hashed=by_set[k]['field_sha256']['u']
        for suffix,sha in zip(('.ids','.u'),hashed,strict=True):verified(stem.with_suffix(suffix),sha)
        meta=read(stem.with_suffix('.json'))
        assert meta['source_sha256']==proof['rst_sha256'] and meta['set']==k and meta['unit'].lower()=='mm'
        numbers=np.fromfile(stem.with_suffix('.ids'),'<i4');u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
        order=np.argsort(numbers)
        fields.append(u[order][positions(numbers[order],ids)])
        field_hashes.append(dict(native_set=k,ids_sha256=hashed[0],U_sha256=hashed[1]))
    grid=raw.grid.cell_data
    contact_ids=grid['ansys_elem_num'][(grid['ansys_etype']==862)&np.isin(grid['ansys_real_constant'],[861,862])]
    ordered=np.argsort(raw.mesh.enum);elems=raw.mesh.elem
    loaded=set();root_values=[]
    root_elements=np.flatnonzero((t[:,:4]==root).any(1))+1200001
    assert len(root_elements)>1
    for station in sets:
        enum,data,_=raw.element_solution_data(station-1,'EMN')
        indices=positions(enum,contact_ids)
        active=[int(cid) for cid,i in zip(contact_ids,indices,strict=True)
                if data[i] is not None and len(data[i]) and max(data[i][:4])>=2]
        for j in ordered[positions(raw.mesh.enum[ordered],np.array(active,dtype=int))]:
            loaded.update(int(n)-OFFSET for n in elems[j][10:18])
        n,s=corners(raw,station-1,'ENS',root_elements,6)
        zz=s[n==node,2]
        np.testing.assert_array_equal(n.reshape(-1,4),OFFSET+t[root_elements-1200001,:4])
        xx=x[t[root_elements-1200001]]
        volume,average=native_average(xx-xx[:,:1],s[:,2].reshape(-1,4))
        root_values.append(dict(volume_mm3=volume,star_mean_MPa=average,native_set=station,
             travel_mm=proof['states'][station-1]['travel_mm'],max_MPa=float(zz.max()),min_MPa=float(zz.min())))
    if node==2100046:
        summary=read(AUDIT/f'{CASE}_{STAMP}_tab_corners.json')
        assert summary['checkpoint_sha256']==digest(record)
        peak=summary['stations'][-1]['metrics']['layer_tension_MPa']
        assert peak['node']==node and abs(root_values[-1]['max_MPa']-peak['peak'])<1e-7
    return dict(xyz=x,connectivity=t,root_node=root,distance=distance,skin=skin,D=material(rules),native_ids=ids,
        u=np.stack(fields),tied=np.concatenate(list(rings.values()))-OFFSET,loaded_contact_nodes=loaded,sets=sets,
        native_corner=root_values,checkpoint_sha256=digest(record),DPF_source_sha256=proof['rst_sha256'],
        field_hashes=field_hashes,mesh_sha256=spec['mesh_sha256'],input_sha256=spec['input_sha256'],step_sha256=STEP_HASH)


def run():
    WORK.mkdir(exist_ok=True)
    lock=(WORK/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    write_json(WORK/'worker.json',dict(pid=os.getpid(),case=CASE,checkpoint=STAMP))
    results={}
    for name,node in [('native_layer_peak',2100046),('nylon_high_Y_root',2100021)]:
        if shutil.disk_usage(ROOT).free<400_000_000_000:raise RuntimeError('Host storage reserve reached')
        source=setup(node)
        base={k:source[k] for k in ('checkpoint_sha256','DPF_source_sha256','field_hashes','mesh_sha256','input_sha256','step_sha256')}
        requested=[(radius,level,False,False) for radius,levels in ((1.8,range(4)),(2.75,range(4)),(3.75,range(3))) for level in levels]
        requested.extend((1.8,level,True,False) for level in (1,2,3))
        requested.extend((1.8,level,False,True) for level in (0,2))
        rows=[]
        for radius,level,alternate,higher in requested:
            if shutil.disk_usage(ROOT).free<400_000_000_000:raise RuntimeError('Host storage reserve reached')
            result=compute(source,radius,level,alternate,higher)
            rows.append(result)
            write_json(WORK/'progress.json',dict(region=name,node=node,completed=len(rows),requested=len(requested),last=result))
            print(name,radius,level,alternate,higher,result['high_Y_root_max_layer_tension_MPa'][-1],result['first_sample_above_coupon_native_set'],flush=True)
            if result['subdivisions']==1:
                assert np.max(abs(np.asarray(result['high_Y_root_max_layer_tension_MPa'])-[v['max_MPa'] for v in source['native_corner']]))<.30
                assert max(result['max_node_error_relative_to_native_um'])<.1
        results[name]=dict(**base,root_node=node,root_xyz_mm=source['xyz'][node-OFFSET].tolist(),
                          native=source['native_corner'],independent=rows)
        write_json(WORK/(name+'.json'),results[name])
    write_json(OUTPUT,dict(case=CASE,checkpoint=STAMP,regions=results,
        shared_patch_solver_sha256=digest(ROOT/'model/snug_tab_submodel.py'),
        scope='Independent small-strain orthotropic patch refinement at the native aluminium layer-stress peak and the prior nylon high-Y root. '
              'Rigid motion is fitted and removed. Native quadratic cut displacements drive each patch; loaded contact faces and tied screw nodes stay outside it. '
              'These local solutions do not redistribute assembly loads or establish fracture. Native post-scope stations remain numerical diagnostics.'))
    write_json(WORK/'complete.json',dict(output_sha256=digest(OUTPUT)))


if __name__=='__main__':
    run()

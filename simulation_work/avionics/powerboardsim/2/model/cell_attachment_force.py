"""Recover modal force transfer on both sides of the six cell-to-strip bonds."""
import argparse
from pathlib import Path

import numpy as np

from audit_local import ROOT,read
from case_stress import source
from film_identity import digest,verified,write_json
from independent_psd import moments,spectrum_input
from seeded_motion import FRAMES,FS,participation
from study_cases import native_case


def bodies_and_bonds(result,geometry):
    grid=result.grid.cell_data
    types=grid['ansys_elem_type_num']
    reals=grid['ansys_real_constant']
    order=np.argsort(result.mesh.enum)
    raw=result.mesh.elem

    def connectivity(mask):
        numbers=np.sort(grid['ansys_elem_num'][mask])
        indices=order[np.searchsorted(result.mesh.enum[order],numbers)]
        assert np.array_equal(result.mesh.enum[indices],numbers)
        return numbers,[raw[i][10:] for i in indices]

    cell_materials=tuple(map(int,geometry))
    # These six native material IDs identify the strip STEP solids in the CAD audit.
    from case_fit import GROUPS
    fit=read(ROOT/'validation/rigid_case_drawdown.json')
    strip_materials=[r['native_material'] for r in fit['records'] if r['STEP_body'] in GROUPS['nickel']]
    assert len(strip_materials)==6
    bodies={}
    for material in [*cell_materials,*strip_materials]:
        elements,connect=connectivity((grid['ansys_material_type']==material)&(types==187))
        connect=np.stack(connect);assert connect.shape==(len(elements),10)
        ids,indices=np.unique(connect,return_inverse=True)
        bodies[material]=(elements,ids,indices.ravel())
    pairs={}
    # The global controls add new hardware pairs at 850 and above.
    for real in np.unique(reals[np.isin(types,[170,174])&(reals<850)]):
        masks={}
        for et,materials in [(170,cell_materials),(174,strip_materials)]:
            _,ns=connectivity((types==et)&(reals==real))
            if not ns:continue
            nodes=np.unique(np.concatenate(ns))
            for mat in materials:
                common=np.intersect1d(nodes,bodies[mat][1])
                if len(common):
                    assert et not in masks
                    masks[et]=(mat,common)
        if set(masks)=={170,174}:pairs[int(real)]=[masks[170],masks[174]]
    assert len(pairs)==6 and {p[1][0] for p in pairs.values()}==set(strip_materials)
    coordinates={}
    for mat in cell_materials:
        ends=[(real,p[0][1]) for real,p in pairs.items() if p[0][0]==mat]
        assert len(ends)==2 and not np.intersect1d(ends[0][1],ends[1][1]).size
        for real,ids in ends:
            idx=np.searchsorted(result.mesh.nnum,ids)
            assert np.array_equal(result.mesh.nnum[idx],ids)
            y=result.mesh.nodes[idx,1]*1000
            assert np.ptp(y)<.1
            coordinates[real]=float(np.mean(y))
        assert max(coordinates[r] for r,_ in ends)-min(coordinates[r] for r,_ in ends)>69
    return bodies,pairs,coordinates


def rms_force(shapes,cov):
    return np.sqrt(np.maximum(0,np.einsum('...m,mn,...n->...',shapes,cov,shapes,optimize=True)))


def locked_pocket(r,faces):
    """Find every case tetrahedron contributing a nodal force on an active PLA contact triangle."""
    order=np.argsort(r.mesh.enum)
    where=order[np.searchsorted(r.mesh.enum[order],faces)]
    assert np.array_equal(r.mesh.enum[where],faces)
    raw=r.mesh.elem
    assert all(raw[i][1]==853 for i in where)
    nodes=np.unique(np.stack([raw[i][10:18] for i in where]))
    grid=r.grid.cell_data
    elements=np.sort(grid['ansys_elem_num'][(grid['ansys_elem_type_num']==187)&(grid['ansys_material_type']==850)])
    where=order[np.searchsorted(r.mesh.enum[order],elements)]
    assert np.array_equal(r.mesh.enum[where],elements)
    conn=np.stack([raw[i][10:20] for i in where]);use=np.isin(conn,nodes)
    near=use.any(axis=1)
    assert np.array_equal(nodes,np.unique(conn[use]))
    return elements[near],use[near],nodes


def modal_transfer(r,geometry,active_case_faces=None):
    bodies,pairs,positions=bodies_and_bonds(r,geometry)
    reals=list(pairs)
    modes=r.nsets
    transfer=np.empty((6,3,modes))
    opposite=np.empty_like(transfer)
    mass_result=np.empty((3,3,modes))
    off_patch=[];check_fields=[]
    # Sampling the first ten actual tetrahedra of each body checks native PSD ENF
    # components separately from the resultant formed by summing signed forces.
    sample_ids=np.concatenate([es[:10] for es,_,_ in bodies.values()])
    pocket=None
    if active_case_faces is not None:
        near,participates,nodes=locked_pocket(r,active_case_faces)
        pocket=dict(cell=np.zeros((3,modes)),case=np.zeros((3,modes)),case_nodes=nodes.tolist(),
                    active_contact_elements=list(active_case_faces))
    for k in range(modes):
        enum,values,_=r.element_solution_data(k,'ENF')
        if pocket is not None:
            ip=np.searchsorted(enum,near);assert np.array_equal(enum[ip],near)
            pla=np.stack([values[i] for i in ip]).reshape(len(near),3,10,3)
            assert np.isfinite(pla).all() and not np.any(pla[:,1])
            pocket['case'][:,k]=pla.sum(axis=1,dtype=float)[participates].sum(axis=0)
        forces={}
        for mat,(elements,ids,conn) in bodies.items():
            ix=np.searchsorted(enum,elements);assert np.array_equal(enum[ix],elements)
            blocks=np.stack([values[j] for j in ix]).reshape(len(elements),3,10,3)
            assert np.isfinite(blocks).all() and not np.any(blocks[:,1])
            # In an undamped eigenvector, static and inertial contributions
            # cancel at free nodes. The residual acts across bonded interfaces.
            summed=np.zeros((len(ids),3))
            np.add.at(summed,conn,blocks.sum(1,dtype=np.float64).reshape(-1,3))
            forces[mat]=summed
        check_fields.append(np.stack([values[j][:30] for j in np.searchsorted(enum,sample_ids)]))
        for j,ends in enumerate(pairs.values()):
            for dest,(mat,ids) in zip((transfer,opposite),ends,strict=True):
                pos=np.searchsorted(bodies[mat][1],ids)
                dest[j,:,k]=forces[mat][pos].sum(0)
        for ci,mat in enumerate(map(int,geometry)):
            attached=np.concatenate([p[0][1] for p in pairs.values() if p[0][0]==mat])
            interior=~np.isin(bodies[mat][1],attached)
            scale=np.linalg.norm(forces[mat])
            if pocket is not None and mat==191:
                pocket['cell'][:,k]=forces[mat][interior].sum(axis=0)
            else:
                off_patch.append(np.linalg.norm(forces[mat][interior])/scale)
            mass_result[ci,:,k]=forces[mat].sum(0)
    opposition=np.linalg.norm(transfer+opposite,axis=1)/np.linalg.norm(transfer,axis=1)
    assert max(off_patch)<1.e-4 and opposition.max()<1.e-4
    if pocket is not None:
        error=np.linalg.norm(pocket['cell']+pocket['case'],axis=0)
        per_mode=np.linalg.norm(transfer,axis=(0,1))+np.linalg.norm(pocket['cell'],axis=0)
        relative=float(np.max(error/per_mode))
        assert relative<1e-4,relative
        pocket['max_two_side_residual_relative_to_interface_forces']=relative
    field=np.moveaxis(np.stack(check_fields),0,-1)
    return transfer,mass_result,pairs,positions,sample_ids,field,float(max(off_patch)),float(opposition.max()),pocket


def recover(branch,campaign):
    basis,folder,r=source(branch+'_basis',campaign)
    cell=read(ROOT/'validation/cell_force'/(branch+'.json'))
    assert cell['basis_rst_sha256']==basis['rst_sha256']
    geometry=cell['geometry']
    log=folder/'solve.out';verified(log,cell['modal_listing_sha256'])
    active=None
    if branch.startswith('snug125_'):
        contact=read(ROOT/'validation/snug125'/(branch+'_static_contacts.json'))
        assert contact['rst_sha256']==cell['static_rst_sha256'] and contact['campaign']==campaign
        group,=contact['contact_history'][-1]['loaded_case_faces']
        assert group['STEP_face']==17
        active=group['element_ids']
    transfer,mass_result,pairs,positions,sample_ids,field,free_error,side_error,pocket=modal_transfer(r,geometry,active)
    reals=list(pairs)
    modes=r.nsets
    cache=ROOT/'.runtime/post'/campaign/(branch+'_basis')/'cell_mass_mean.npz'
    verified(cache,cell['mean_shapes_sha256'])
    with np.load(cache) as d:
        assert list(d['materials'])==list(map(int,geometry)) and np.array_equal(d['frequencies_Hz'],r.time_values)
        means=d['mean']
    mass=np.array([g['mass_kg'] for g in geometry.values()])
    expected=mass[:,None,None]*means*(2*np.pi*r.time_values)**2
    modal_check=np.linalg.norm(expected-mass_result,axis=(0,1))/np.linalg.norm(expected,axis=(0,1))
    print(branch,'mode checks: off-patch, opposition, mass',free_error,side_error,modal_check.max(),flush=True)
    assert modal_check.max()<5.e-4
    shape_file=cache.with_name('attachment_modes.npz')
    if not shape_file.exists():
        tmp=shape_file.with_suffix('.new.npz')
        extra={} if pocket is None else {'middle_cell_pocket_force':pocket['cell']}
        np.savez_compressed(tmp,force=transfer,pairs=reals,frequency_Hz=r.time_values,**extra)
        tmp.replace(shape_file)
    with np.load(shape_file) as saved:
        assert np.array_equal(saved['pairs'],reals) and np.array_equal(saved['frequency_Hz'],r.time_values)
        assert np.array_equal(saved['force'],transfer)
        if pocket is not None:assert np.array_equal(saved['middle_cell_pocket_force'],pocket['cell'])
    records={}
    for axis in 'XYZ':
        path,fk,sk,damping=spectrum_input(axis)
        gamma=participation(log.read_text(errors='replace'),axis)
        cov,_=moments(r.time_values,gamma,fk,sk,damping,.125)
        coarse,_=moments(r.time_values,gamma,fk,sk,damping,.25)
        result=rms_force(transfer,cov)
        convergence={}
        for hz in [2000,3000,3500,4000]:
            n=np.searchsorted(r.time_values,hz,side='right')
            partial=rms_force(transfer[:,:,:n],cov[:n,:n])
            convergence[hz]=dict(modes=int(n),component_max_absolute_change_N=float(abs(partial-result).max()),
                                 driven_max_relative_change=float(np.max(abs(partial[:,'XYZ'.index(axis)]/result[:,'XYZ'.index(axis)]-1))))
        native=None
        key=native_case(branch,'psd_'+axis)
        if (ROOT/'validation/global'/(key+'.json')).exists():
            proof,_,nat=source(key,campaign)
            en,v,_=nat.element_solution_data([3,1],'ENF')
            ix=np.searchsorted(en,sample_ids);assert np.array_equal(en[ix],sample_ids)
            actual=np.stack([v[j][:30] for j in ix])
            estimate=rms_force(field,cov)
            component_norm=np.linalg.norm((estimate-actual).reshape(-1,3),axis=0)/np.linalg.norm(actual.reshape(-1,3),axis=0)
            print(branch,axis,'PSD element forces',component_norm,flush=True)
            assert max(component_norm)<.005
            native=dict(case=key,rst_sha256=proof['rst_sha256'],elements=len(ix),relative_L2_XYZ=component_norm.tolist())
        clip_case=native_case(branch,'motion_'+axis)
        clip_record=read(ROOT/'validation/independent_motion'/(clip_case+'.json'))
        assert clip_record['basis_rst_sha256']==basis['rst_sha256'] and clip_record['axis']==axis
        clip=ROOT/'.runtime/post'/campaign/clip_case/'independent/coordinates.npz'
        verified(clip,clip_record['clip_sha256'])
        with np.load(clip) as samples:
            assert np.array_equal(samples['time_s'],FRAMES/FS)
            assert np.array_equal(samples['frequencies_Hz'],r.time_values)
            frame_forces=samples['coordinates']@transfer.reshape(-1,modes).T
        peak=np.abs(frame_forces).max(0).reshape(6,3)
        cells={}
        for i,mat in enumerate(map(int,geometry)):
            js=sorted([j for j,p in enumerate(pairs.values()) if p[0][0]==mat],key=lambda j:positions[reals[j]])
            total=rms_force(transfer[js].sum(0),cov)
            ref=cell['base_cases'][axis]['cells'][str(mat)]['net_dynamic_force_XYZ_rms_N']
            cross=np.einsum('dm,mn,dn->d',transfer[js[0]],cov,transfer[js[1]])
            correlation=cross/np.prod(result[js],axis=0)
            assert np.max(abs(correlation))<=1+1e-8
            assert np.allclose(total**2,np.sum(result[js]**2,axis=0)+2*cross,atol=1e-10)
            cells[mat]=dict(end_correlation_XYZ=correlation.tolist(),ends=[dict(pair=reals[j],strip_material=pairs[reals[j]][1][0],face_y_mm=positions[reals[j]],
                     cell_nodes=len(pairs[reals[j]][0][1]),nickel_nodes=len(pairs[reals[j]][1][1]),
                     transfer_XYZ_N_rms=result[j].tolist(),seeded_clip_peak_abs_XYZ_N=peak[j].tolist()) for j in js],summed_signed_transfer_XYZ_N_rms=total.tolist(),
                     absolute_cell_inertia_XYZ_N_rms=ref)
        records[axis]=dict(spectrum_sha256=digest(path),independent_clip_sha256=clip_record['clip_sha256'],cells=cells,cutoffs_Hz=convergence,native_element_PSD=native,
                 quadrature_change_relative=float(np.max(abs(result/rms_force(transfer,coarse)-1))))
        if pocket is not None:
            others=[j for j,pair in enumerate(pairs.values()) if pair[0][0]==191]
            mid=list(map(int,geometry)).index(191)
            closure=transfer[others].sum(axis=0)+pocket['cell']-mass_result[mid]
            assert np.linalg.norm(closure)<1.e-10*np.linalg.norm(mass_result[mid])
            records[axis]['middle_pocket_dynamic_XYZ_RMS_N']=rms_force(pocket['cell'],cov).tolist()
            records[axis]['middle_bonds_plus_pocket_XYZ_RMS_N']=rms_force(mass_result[mid],cov).tolist()
    extra={}
    contact_state='with the cell-to-case gaps held open'
    if pocket is not None:
        extra['middle_pocket']={k:v for k,v in pocket.items() if k not in ('case','cell')}
        contact_state='with the installed middle pocket in contact and the two outer pockets open'
    write_json(ROOT/'validation/cell_attachment'/f'{branch}.json',dict(branch=branch,campaign=campaign,
            modal_rst_sha256=basis['rst_sha256'],shape_force_sha256=digest(shape_file),cell_inertia_record_sha256=digest(ROOT/'validation/cell_force'/(branch+'.json')),
            largest_relative_unbalanced_free_node_norm=free_error,largest_two_side_modal_residual=side_error,
            largest_whole_cell_modal_force_error=modal_check.max(),spectrum=records,**extra,
            scope='Independent modal combination of native bonded-interface eigenvector force resultants. Dynamic component '
                  f'only, {contact_state}. The bond forces describe the two complete cell-to-nickel bonds on each cell. The seeded peaks use the 480 historical movie frames.'))



def check_native_clip(branch,campaign,axis,coordinates):
    record=read(ROOT/'validation/cell_attachment'/(branch+'.json'))
    source_file=ROOT/'.runtime/post'/campaign/(branch+'_basis')/'attachment_modes.npz'
    verified(source_file,record['shape_force_sha256'])
    reference=record['spectrum'][axis]
    clip=ROOT/'.runtime/post'/campaign/native_case(branch,'motion_'+axis)/'independent/coordinates.npz'
    verified(clip,reference['independent_clip_sha256'])
    with np.load(source_file) as fields,np.load(clip) as independent:
        assert np.array_equal(fields['frequency_Hz'],independent['frequencies_Hz'])
        forces=fields['force'].reshape(-1,len(fields['frequency_Hz'])).T
        native=coordinates[FRAMES]@forces
        previous=independent['coordinates']@forces
        peaks=np.max(abs(native),axis=0).reshape(-1,3)
        pairs=fields['pairs'].tolist()
    rel=np.linalg.norm(native-previous)/np.linalg.norm(previous)
    assert rel<.005 and np.isfinite(peaks).all()
    return dict(native_vs_independent_clip_relative_L2=float(rel),
                max_sampled_difference_N=float(np.max(abs(native-previous))),
                peak_abs_XYZ_N_by_bond=dict(zip(pairs,peaks.tolist(),strict=True)),
                force_shape_sha256=record['shape_force_sha256'])


def october(archive,campaign):
    from native_rst import read_rst
    history=read(ROOT/'validation/cell_force/october_native_history.json')
    assert history['campaign']==campaign
    old=archive/'outputs/random_vibration_20261005_0950/modal_basis/file.rst'
    verified(old,history['old_basis_sha256'])
    r=read_rst(old)
    ref=read(ROOT/'validation/cell_force/bare.json')
    record=read(ROOT/'validation/cell_attachment/bare.json')
    field=ROOT/'.runtime/post'/campaign/'bare_basis/attachment_modes.npz'
    verified(field,record['shape_force_sha256'])
    force,_,pairs,_,_,_,free,side,_=modal_transfer(r,ref['geometry'])
    with np.load(field) as new:
        assert np.allclose(r.time_values,new['frequency_Hz'],atol=0,rtol=1e-5)
        assert list(pairs)==new['pairs'].tolist()
        fresh=new['force'].reshape(-1,r.nsets).T
    previous=force.reshape(-1,r.nsets).T
    results={}
    for axis in 'XYZ':
        hist=history['base_cases'][axis]
        old_q=ROOT.parent/'1/output/latex/random_vibration/reproduction/motion/inputs'/f'modal_coordinates_{axis}_clip.csv'
        verified(old_q,hist['clip_csv_sha256'])
        q=np.loadtxt(old_q,delimiter=',',skiprows=1)
        assert q.shape==(len(FRAMES),1+r.nsets) and np.allclose(q[:,0],FRAMES/FS,atol=5.1e-7,rtol=0)
        comp=ROOT/'.runtime/post'/campaign/('bare_motion_'+axis)/'independent/coordinates.npz'
        verified(comp,record['spectrum'][axis]['independent_clip_sha256'])
        with np.load(comp) as new:
            assert np.array_equal(new['time_s'],FRAMES/FS)
            now=new['coordinates']@fresh
        historic=q[:,1:]@previous
        diff=now-historic
        rel=np.linalg.norm(diff,axis=0)/np.linalg.norm(historic,axis=0)
        print(axis,'October end force check',rel.max(),abs(diff).max(),flush=True)
        assert rel.max()<.002
        results[axis]=dict(original_MCF_clip_sha256=hist['clip_csv_sha256'],original_MCF_sha256=hist['mcf_sha256'],
                new_independent_clip_sha256=record['spectrum'][axis]['independent_clip_sha256'],
                maximum_component_relative_L2=float(rel.max()),max_sample_difference_N=float(abs(diff).max()))
    write_json(ROOT/'validation/cell_attachment/october_native_clip.json',dict(original_basis_sha256=history['old_basis_sha256'],
        original_mcf_check_sha256=digest(ROOT/'validation/cell_force/october_native_history.json'),
        repeat_basis_sha256=record['modal_rst_sha256'],repeat_force_shapes_sha256=record['shape_force_sha256'],
        frames=len(FRAMES),pairs=list(pairs),axes=results,original_max_free_node_norm=free,original_two_side_residual=side,
        scope='October native modal coordinates and original mode forces compared in physical coordinates to the fresh '
              'native basis with independent seeded motion. Both calculations resolve simultaneous forces on all six bonds.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('branch',choices=['bare','stand3_nylon','stand3_aluminium','snug125_nylon','snug125_aluminium','snug125_nylon_mesh15','snug125_aluminium_mesh15','october'])
    p.add_argument('--october-archive',type=Path);p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args()
    if a.branch=='october':
        if not a.october_archive:p.error('October control requires --october-archive')
        october(a.october_archive,a.campaign)
    else:recover(a.branch,a.campaign)

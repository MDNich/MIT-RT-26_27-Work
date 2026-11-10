"""Separate left-cell travel due to relative roll from motion at the height of the flat nickel legs."""
import argparse
import numpy as np
from scipy.spatial.transform import Rotation

from audit_local import ROOT,read
from basis_comparison import field_files
from case_stress import source
from cell_rigid_fit import body_mass,check_pose,fit,pose_operator,strip_height
from film_identity import digest,verified,write_json
from local_equilibrium import positions
from motion_surface import displacement_basis
from pull_pose_clearance import rigid_pose
from seeded_motion import FS
from snug_board_pull import BRANCHES,CAMPAIGN,REFERENCE,mass_weights
from snug_edge_cell_travel import get_geometry,surface_transfer,verify_extrema
from snug_pla_vibration import full_coordinates
from stage_snug_fit import AUDIT
from tab_seating import read_point_file


def local():
    from snug_bare_pull_poses import bare_poses
    stem='lateral_friction_locked'
    pilot,history,poses,source_record=bare_poses(stem)
    height=strip_height()
    checkpoint=read(AUDIT/REFERENCE)
    folder=ROOT/'.runtime/qa/snug125/forward-readback'/checkpoint['checkpoint']
    spec=read(folder/'dpf_points/request.json');nodes=np.array(spec['nodes'])
    assert spec['source_sha256']==checkpoint['rst_sha256'] and spec['sets']==list(range(1,34))
    u,_=read_point_file(folder/'pull.rst',folder/'dpf_points',checkpoint['rst_sha256'],spec['sets'],spec['nodes'])
    mesh_file=ROOT/'.runtime/local_inputs'/stem/'mesh.json'
    verified(mesh_file,read(ROOT/'validation/local_inputs.json')[stem]['files']['mesh.json'])
    mesh=read(mesh_file);att=np.array(mesh['attachment'])
    initial=np.array([mesh['nodes'][str(n)] for n in att])
    assert np.array_equal(pilot,mesh['nodes'][str(mesh['pilot'])])
    cased_poses=[rigid_pose(initial,initial+field[positions(nodes,att)],pilot) for field in u]
    config=read(ROOT/'.runtime/local_inputs'/stem/'config.json')
    assert np.max(abs(u[9:11,positions(nodes,np.array(config['target_pilots'])),0]))<1.e-10
    archive=ROOT/'.runtime/archive'/CAMPAIGN/('bare_'+stem)
    manifest=read(ROOT/'.runtime/receipts'/CAMPAIGN/('bare_'+stem)/'archived.json')
    hashes={r['name']:r['sha256'] for r in manifest['files']}
    verified(archive/'model.inp',hashes['model.inp'])
    deck=(archive/'model.inp').read_text().upper().splitlines()
    # Both original washer planes can move only in Z before lock. During the
    # pull all four target pilots retain their X and rotational constraints.
    for node in config['target_pilots']:
        assert f'D,{node},ALL,0' in deck
        assert all(s==f'DDELE,{node},UZ' for s in deck if s.startswith(f'DDELE,{node},'))
    ref=read(AUDIT/'whole_board_initial_comparison.json')
    measured={}
    for name,states,force in [('bare',poses,history['fx_N']),('snug125_nylon',cased_poses,
                              [r['cell_force_N'] for r in checkpoint['states']])]:
        lo,hi=9,10
        q0,d0,e0=states[lo];q1,d1,e1=states[hi]
        F=force[hi]-force[lo]
        dx=1000*(d1[0]-d0[0])/F
        delta_z=np.array([0.,0.,height])
        roll=-1000*(q1.apply(delta_z)-q0.apply(delta_z))[0]/F
        spin=(q1*q0.inv()).as_rotvec()/F
        assert abs(dx-ref['initial_local_fixture_increment_um_per_N'])<.001
        assert max(e0,e1)<1e-5 and max(abs(spin[[0,2]]))<1e-8
        guess=-1000*height*spin[1]
        assert abs(guess-roll)<.0001
        measured[name]=dict(centre_X_um_per_N=dx,roll_X_um_per_N=roll,strip_height_X_um_per_N=dx-roll,
                   Y_rotation_mrad_per_N=1000*spin[1],roll_fraction=roll/dx,
                   native_sets=[lo+1,hi+1],force_N=[force[lo],force[hi]],max_rigid_fit_error_mm=max(e0,e1))
    write_json(AUDIT/'initial_local_cell_roll.json',dict(cases=measured,offset_above_mass_centre_mm=height,
               bare=source_record,snug_checkpoint_sha256=digest(AUDIT/REFERENCE),
               snug_DPF_sha256=digest(folder/'dpf_points/displacements.bin'),scope='Finite rotation of each native rigid cell, '
               'measured at two shared equilibria before the left cell loads the case.'))


def run(branch,method):
    basis,folder,raw=source(branch+'_basis',CAMPAIGN)
    static,_,parent=source(branch+'_static',CAMPAIGN)
    modal,_,freq,geom,relative,_,cell,_,control=get_geometry(branch,CAMPAIGN)
    assert basis['rst_sha256']==modal['rst_sha256']==geom['basis_sha256']
    ns,W,rec=mass_weights(branch)
    ids=ns[W[0]!=0];w=W[0,W[0]!=0]
    assert rec['basis_rst_sha256']==basis['rst_sha256'] and rec['static_rst_sha256']==static['rst_sha256']
    M,geometry=body_mass(parent,ids,w,rec['geometry']['176']['volume_m3'])
    x=1000*raw.mesh.nodes[positions(raw.mesh.nnum,ids)]
    operator=pose_operator(M,x)
    fields=field_files(basis['case'],CAMPAIGN,basis['rst_sha256'],len(freq)) if branch!='bare' else None
    shape=1000*displacement_basis(raw,ids,fields)
    translation,spin=fit(operator,shape)
    assert np.allclose(translation,cell,rtol=1e-10,atol=1e-8)
    v=np.array([.2,.35,-.1]);testrot=np.array([.001,-.003,.002])
    a,b=fit(operator,(v+np.cross(testrot,operator[1]))[None])
    assert np.allclose(a[0],v,atol=1e-12,rtol=0) and np.allclose(b[0],testrot,atol=1e-12,rtol=0)
    groups,washer_ids,xyz,port,modes,_=control
    flat=1000*parent.mesh.nodes[positions(parent.mesh.nnum,washer_ids)]
    centres=[np.array(geom['washer_faces'][i]['fixture_lower_platen_centre_mm']) for i in groups]
    hole=read(ROOT/'.runtime/local_inputs/lateral_friction_locked/config.json')['hole_radius_mm']
    washer=surface_transfer(groups,washer_ids,xyz,flat,modes,port,centres,hole,5)['whole']
    assert np.allclose(translation-washer['transfer'],relative,rtol=0,atol=1e-8)
    height=strip_height()
    rot=spin-washer['rot']
    curve=np.column_stack((relative[:,0],-height*rot[:,1],relative[:,0]+height*rot[:,1]))
    assert np.max(abs(curve[:,0]-curve[:,1]-curve[:,2]))<1e-8
    def snapshot(q):
        centre,rock,gauge=1000*(q@curve)
        uc=(q@shape.reshape(len(freq),-1)).reshape(-1,3)
        finite=check_pose(M,operator,uc)
        assert np.max(abs(np.array(finite['small_rotvec_rad'])-q@spin))<1e-11
        return dict(centre_X_um=centre,roll_X_um=rock,strip_height_X_um=gauge,roll_fraction=rock/centre if centre else None,
                    cell_Y_rotation_mrad=float(1000*q@spin[:,1]),clamps_Y_rotation_mrad=float(1000*q@washer['rot'][:,1]),
                    cell_pose_check=finite)
    static_q=cell[:,0]/1000/(2*np.pi*freq)**2
    low=snapshot(static_q)
    previous=read(AUDIT/f'{branch}_cell_flexibility.json') if branch in BRANCHES else None
    if previous:
        assert previous['basis_sha256']==basis['rst_sha256']
        assert abs(low['centre_X_um']-previous['cutoff_Hz']['4000']['left_relative_to_its_clamps_X_um_per_N'])<1e-9
    def verify_stations(coordinates, snapshots):
        frame=verify_extrema(*control,coordinates,coordinates@relative,return_rotations=True)
        washer_small=np.asarray(frame['small_rotvec_rad'])
        assert abs(washer_small-coordinates@washer['rot']).max()<1.e-9
        dz=np.array([0.,0.,height])
        for state,clamp_R,centre_correction in zip(snapshots,frame['finite_rotation_matrices'],
                                   frame['finite_rotation_minus_linear_X_mm_at_extrema'],strict=True):
            cell_R=Rotation.from_rotvec(state['cell_pose_check']['finite_rotvec_rad'])
            finite_roll=1000*((clamp_R@dz)[0]-cell_R.apply(dz)[0])
            state['finite_pose_roll_X_um']=finite_roll
            state['finite_pose_strip_height_X_um']=state['centre_X_um']+1000*centre_correction-finite_roll

    verify_stations(static_q[None], [low])
    motion={}
    old=read(AUDIT/f'{branch}_edge_cell_travel_{method}.json')
    assert old['geometry']['basis_sha256']==basis['rst_sha256']
    for axis in 'XYZ':
        q,sha,drive=full_coordinates(branch,CAMPAIGN,method,axis,basis,folder,freq)
        values=1000*(q@curve)
        extrema={};ref=old['axes'][axis]
        assert (sha,drive)==(ref['coordinate_source_sha256'],ref['excitation_sha256'])
        for col,label in enumerate(('centre','roll','strip_height')):
            extrema[label]={}
            for name,ind in [('negative',int(values[:,col].argmin())),('positive',int(values[:,col].argmax()))]:
                if col==0:assert ind==ref[name+'_X']['sample']
                check=snapshot(q[ind])
                assert np.allclose([check[k] for k in ('centre_X_um','roll_X_um','strip_height_X_um')],values[ind],atol=1e-8,rtol=0)
                extrema[label][name]=dict(sample=ind,time_s=ind/FS,**check)
        ordered=[data for record in extrema.values() for data in record.values()]
        verify_stations(q[[state['sample'] for state in ordered]],ordered)
        motion[axis]=dict(coordinate_source_sha256=sha,drive_sha256=drive,extrema=extrema)
    write_json(AUDIT/f'{branch}_cell_roll_{method}.json',dict(branch=branch,method=method,basis_sha256=basis['rst_sha256'],
               static_sha256=static['rst_sha256'],offset_above_mass_centre_mm=height,geometry=geometry,
               mass_weights_sha256=rec['mass_weights_sha256'],strip_height_reference='Virtual point directly above the centroid '
               'at the same 10.625 mm offset as the nickel flat-leg midsurface in the local fixture.',
               small_load_per_newton=low,axes=motion,scope='Linearized cell and washer poses about bolt lock. '
               'The roll term is the part of centre X travel associated with Y-axis rotation relative to both clamps.'))
    print(branch,method,low['roll_X_um'],[(a,motion[a]['extrema']['centre']['positive']['roll_fraction']) for a in 'XYZ'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('branch',choices=(*BRANCHES,'snug125_nylon_mesh15','local'))
    p.add_argument('--method',choices=('native','exact'),default='native')
    args=p.parse_args()
    if args.branch=='local':local()
    else:run(args.branch,args.method)

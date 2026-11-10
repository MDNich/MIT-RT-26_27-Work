"""Compare left-cell side loading on three complete installed boards with the original local fixture."""
import argparse
import hashlib
import re

import numpy as np

from audit_local import ROOT, read, table
from case_stress import source
from cell_rigid_fit import body_mass, check_pose, fit, pose_operator, strip_height
from scipy.spatial.transform import Rotation
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from native_rst import read_rst
from snug_edge_cell_travel import get_geometry, surface_transfer, verify_extrema
from snug_equilibrium_residual import accepted_substeps
from stage_local_jobs import seal
from stage_snug_fit import AUDIT, INPUTS, MESH, STEP_HASH, input_record
from tab_seating import read_point_file

CAMPAIGN='nov08_01'
BRANCHES=('bare','snug125_nylon','snug125_aluminium')
REGISTRY=AUDIT/'whole_board_pull_inputs.json'
REFERENCE='snug125_nylon_lateral_friction_locked_pin1_m15_ls3_ss24_checkpoint.json'
BODIES=(176,191,187)


def mass_weights(branch):
    evidence=read(ROOT/'validation/cell_force'/f'{branch}.json')
    path=ROOT/'.runtime/post'/CAMPAIGN/(branch+'_basis')/'cell_mass_weights.npz'
    verified(path,evidence['mass_weights_sha256'])
    with np.load(path) as data:
        weights=np.stack([data['weights'][np.flatnonzero(data['materials']==m).item()] for m in BODIES])
        nodes=data['nodes']
    assert np.allclose(weights.sum(1),1.,rtol=0,atol=1e-12)
    assert np.all((weights!=0).sum(0)==1)
    return nodes,weights,evidence


def commands(step, increment, nodes, weights, force):
    lines=['ALLSEL,ALL','CSYS,0','FCUM,REPL','KBC,0',f'TIME,{step}',f'NSUBST,{increment},64,1']
    if force is not None:
        lines.extend(f'F,{int(n)},FX,{force*w:.15e}' for n,w in zip(nodes,weights,strict=True))
    return lines+['SOLVE']


def stage():
    reference=read(AUDIT/REFERENCE)
    common=reference['equal_bare_endpoint_load']['bare']['cell_force_N']
    assert 8.54<common<8.55
    specs={}
    patterns=[]
    for branch in BRANCHES:
        case=branch+'_cellpush_x'
        parent=branch+'_static'
        data,folder,raw=source(parent,CAMPAIGN)
        receipt=ROOT/'.runtime/receipts'/CAMPAIGN/parent
        ledger=read(receipt/'archived.json');state=read(receipt/'status.json')
        assert ledger['case']==parent and state['phase']=='solver_complete' and state['cores']==12
        assert (receipt/'released.txt').is_file()
        if branch!='bare':
            installed=read(AUDIT/(parent+'_installed.json'))
            assert installed['linearization_review_passed'] and installed['rst_sha256']==data['rst_sha256']
        ids,W,evidence=mass_weights(branch)
        assert data['rst_sha256']==evidence['static_rst_sha256']
        last=int(raw._resultheader['ls_table'][-1,1])
        assert raw._resultheader['ls_table'][-1,0]==2 and raw.time_values[-1]==2
        take=W[0]!=0;nodes=ids[take];w=W[0,take]
        ix=positions(raw.mesh.nnum,nodes)
        assert np.max(abs(raw.mesh.node_angles[ix]))<1e-12
        xyz=raw.mesh.nodes[ix]
        centroid=w@xyz
        assert np.allclose(1000*centroid,evidence['geometry']['176']['centroid_mm'],rtol=0,atol=1e-9)
        assert np.linalg.norm(np.cross(xyz-centroid,np.column_stack((common*w,np.zeros((len(w),2))))).sum(0))<1e-12
        assert not np.intersect1d(nodes,raw.mesh.node_components['_FIXEDSU']).size
        files={r['name']:r for r in ledger['files']}
        for name in ['file.rdb','file.ldhi','file.rst',*[f'file{rank}.{ext}' for rank in range(12) for ext in ('r001','rst')]]:
            verified(folder/name,files[name]['sha256'])
        deck=['/BATCH','/SOLU',f'ANTYPE,,REST,2,{last},CONTINUE','ALLSEL,ALL','AUTOTS,ON',
              'CNVTOL,F,1,0.01,2','OUTRES,NSOL,ALL','OUTRES,RSOL,ALL','OUTRES,CONT,ALL','OUTRES,MISC,ALL']
        for step,inc,force in ((3,1,None),(4,2,1.),(5,4,common),(6,4,0.)):
            deck.extend(commands(step,inc,nodes,w,force))
        deck+=['FINISH','/POST1','SET,LAST','/COM,PB_WHOLE_BOARD_PULL_FINISHED','FINISH','/EXIT,NOSAVE']
        dest=INPUTS/case;dest.mkdir(exist_ok=True)
        binary=('\n'.join(deck)+'\n').encode('ascii')
        sha=seal(dest/'model.inp',binary)
        patterns.append(hashlib.sha256('\n'.join(x for x in deck if x.startswith('F,')).encode()).hexdigest())
        specs[case]=dict(case=case,campaign=CAMPAIGN,parent=parent,parent_rst_sha256=data['rst_sha256'],
            parent_ledger_sha256=digest(receipt/'archived.json'),parent_lock_substep=last,native_ranks=12,
            input_sha256=sha,mesh_load_nodes=len(nodes),mass_weights_sha256=evidence['mass_weights_sha256'],
            load_centre_mm=(1000*centroid).tolist(),endpoint_force_N=common,force_cards_sha256=patterns[-1],
            reference_checkpoint_sha256=digest(AUDIT/REFERENCE),case_step_sha256=STEP_HASH if branch!='bare' else None)
    assert len(set(patterns))==1
    if REGISTRY.exists():
        assert read(REGISTRY)==specs
    else:
        write_json(REGISTRY,specs)
    print('Three installed parents verified. All three decks contain the identical left-cell load pattern.')


def forces_and_bolts(raw, indices, supports, pilots):
    result=[];bolts=[]
    for i in indices:
        f,n,d=raw.nodal_reaction_forces(int(i))
        take=np.isin(n,supports)&(d<=3)
        sums=np.bincount(d[take],weights=f[take],minlength=4)[1:4]
        assert len(np.unique(n[take]))==len(supports)
        result.append(sums)
        loads=[]
        for pilot in pilots:
            row=np.flatnonzero((n==pilot)&(d==1)).item()
            loads.append(float(f[row]))
        bolts.append(loads)
    return np.array(result),np.array(bolts)


def cell_roll_states(parent,ids,weights,volume,reference_cell,displacements,centre_motion,washer_spin,pose_check,travel):
    """Resolve the finite rotation contribution at the flat-strip height for the direct-load states."""
    M,measure=body_mass(parent,ids,weights,volume)
    op=pose_operator(M,reference_cell)
    centroid,cell_spin=fit(op,displacements)
    assert np.max(abs(centroid-centre_motion))<1e-8
    height=strip_height()
    dz=np.array([0.,0.,height])
    states=[]
    for j,clamp in enumerate(pose_check['finite_rotation_matrices']):
        fitted=check_pose(M,op,displacements[j])
        cell_rotation=Rotation.from_rotvec(fitted['finite_rotvec_rad'])
        finite_roll=1000*((clamp@dz)[0]-cell_rotation.apply(dz)[0])
        finite_centre=1000*(travel[j,0]+pose_check['finite_rotation_minus_linear_X_mm_at_extrema'][j])
        states.append(dict(cell_Y_mrad=1e3*cell_spin[j,1],clamps_Y_mrad=1e3*washer_spin[j,1],
                    linear_roll_X_um=-1000*height*(cell_spin[j,1]-washer_spin[j,1]),
                    finite_roll_X_um=finite_roll,finite_strip_height_X_um=finite_centre-finite_roll,
                    cell_fit=fitted))
    return states,measure,height


def audit(case):
    spec=read(REGISTRY)[case];parent=spec['parent'];branch=parent.removesuffix('_static')
    assert branch in BRANCHES and case==branch+'_cellpush_x'
    proof,original,locked=source(parent,CAMPAIGN)
    assert proof['rst_sha256']==spec['parent_rst_sha256']
    rec=ROOT/'.runtime/receipts'/CAMPAIGN/case
    ledger=read(rec/'archived.json');state=read(rec/'status.json')
    assert ledger['case']==case and ledger['campaign']==CAMPAIGN and (rec/'released.txt').is_file()
    assert state['native_clean'] and state['exit']==0 and state['parent']==parent and state['cores']==12
    folder=ROOT/'.runtime/archive'/CAMPAIGN/case
    hashes={r['name']:r['sha256'] for r in ledger['files']}
    for name in ('model.inp','file.rst','solve.out'):verified(folder/name,hashes[name])
    assert hashes['model.inp']==spec['input_sha256']
    listing=(folder/'solve.out').read_text(errors='replace')
    assert 'PB_WHOLE_BOARD_PULL_FINISHED' in listing and re.search(r'TOTAL OF\s+12 CORES REQUESTED',listing)
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',listing)
    residuals=accepted_substeps(listing)
    raw=read_rst(folder/'file.rst');times=raw.time_values
    assert np.array_equal(times[:locked.nsets],locked.time_values) and times[-1]==6
    ls=raw._resultheader['ls_table'][:,:2];add=np.arange(locked.nsets,raw.nsets)
    assert np.array_equal(ls[:locked.nsets],locked._resultheader['ls_table'][:,:2])
    assert np.array_equal(ls[add],[[r['step'],r['substep']] for r in residuals])
    assert np.allclose(times[add],[r['load_time'] for r in residuals],rtol=0,atol=1e-4)
    assert max(r['force_residual_N'] for r in residuals)<=.01001
    for end in (3.,4.,5.,6.): assert np.count_nonzero(np.isclose(times,end,rtol=0,atol=1e-9))==1
    mass_ids,W,evidence=mass_weights(branch)
    assert evidence['mass_weights_sha256']==spec['mass_weights_sha256']
    original_ledger=read(ROOT/'.runtime/receipts'/CAMPAIGN/parent/'archived.json')
    assert spec['parent_ledger_sha256']==digest(ROOT/'.runtime/receipts'/CAMPAIGN/parent/'archived.json')
    bolt_file=original/'bolt_preload_audit.csv'
    verified(bolt_file,next(r['sha256'] for r in original_ledger['files'] if r['name']==bolt_file.name))
    bf=table(bolt_file);final=bf[bf['step']==2];pilots=final['pilot'].astype(int)
    assert len(pilots)==6 and np.max(abs(final['reaction_N']-750))<1.
    _,_,_,geom,_,_,_,_,control=get_geometry(branch,CAMPAIGN)
    groups,washer_ids,xyz,port,_,_=control
    nodes=np.unique(np.r_[mass_ids,washer_ids,pilots])
    overlap=locked.nsets-1;steps=np.r_[overlap,add]
    post=ROOT/'.runtime/post'/CAMPAIGN/case
    u,_=read_point_file(folder/'file.rst',post/'cell_load_nodes',hashes['file.rst'],(steps+1).tolist(),nodes.tolist())
    initial,_=read_point_file(original/'file.rst',post/'parent_lock_nodes',spec['parent_rst_sha256'],[locked.nsets],nodes.tolist())
    assert np.max(abs(initial[0]-u[0]))<1.e-7
    supports=np.sort(raw.mesh.node_components['_FIXEDSU'])
    assert len(supports)==781 and np.array_equal(supports,np.sort(locked.mesh.node_components['_FIXEDSU']))
    reactions,bolts=forces_and_bolts(raw,steps,supports,pilots)
    assert np.max(abs(bolts[0]-final['reaction_N']))<1.e-3
    assert np.max(abs(u[:,positions(nodes,pilots),0]-u[0,positions(nodes,pilots),0]))<1.e-6
    zero=np.flatnonzero(np.isclose(times[steps],3.,rtol=0,atol=1.e-9)).item()
    relative=u-u[zero];centre_motion=W@relative[:,positions(nodes,mass_ids)]
    washer_reference=raw.mesh.nodes[positions(raw.mesh.nnum,washer_ids)]*1000
    assert np.max(abs(washer_reference+u[0,positions(nodes,washer_ids)]-xyz))<1.e-6
    original_centres=1000*raw.mesh.nodes[positions(raw.mesh.nnum,mass_ids)]
    assert np.max(abs(W[0]@(original_centres+u[0,positions(nodes,mass_ids)])-port))<1.e-6
    actual_xyz=washer_reference+u[zero,positions(nodes,washer_ids)]
    loaded_port=W[0]@(original_centres+u[zero,positions(nodes,mass_ids)])
    assert np.linalg.norm(loaded_port-port)<.1
    centres=[np.array(geom['washer_faces'][i]['fixture_lower_platen_centre_mm']) for i in groups]
    hole=read(ROOT/'.runtime/local_inputs/lateral_friction_locked/config.json')['hole_radius_mm']
    washer_u=relative[:,positions(nodes,washer_ids)]
    frame=surface_transfer(groups,washer_ids,actual_xyz,washer_reference,washer_u,loaded_port,centres,hole,5)['whole']
    travel=centre_motion[:,0]-frame['transfer']
    pose_check=verify_extrema(groups,washer_ids,actual_xyz,loaded_port,washer_u,centre_motion[:,0],
                              np.eye(len(steps)),travel,return_rotations=True)
    assert np.max(abs(np.asarray(pose_check['small_rotvec_rad'])-frame['rot']))<1e-8
    use=W[0]!=0
    cell_ids=mass_ids[use]
    take=positions(nodes,cell_ids)
    rotation_states,measure,height=cell_roll_states(locked,cell_ids,W[0,use],evidence['geometry']['176']['volume_m3'],
        original_centres[use]+u[zero,take],relative[:,take],centre_motion[:,0],frame['rot'],pose_check,travel)
    applied=np.interp(times[steps],[2.,3.,4.,5.,6.],[0.,0.,1.,spec['endpoint_force_N'],0.])
    residual=reactions-reactions[zero];residual[:,0]+=applied
    assert np.max(abs(residual[zero:])) < .03
    result=dict(case=case,campaign=CAMPAIGN,registry_sha256=digest(REGISTRY),rst_sha256=hashes['file.rst'],
                parent_rst_sha256=spec['parent_rst_sha256'],input_sha256=hashes['model.inp'],listing_sha256=hashes['solve.out'],
                parent_DPF_sha256=digest(post/'parent_lock_nodes/displacements.bin'),native_converged_steps=residuals,
                source_DPF_sha256=digest(post/'cell_load_nodes/displacements.bin'),
                cell_mass_integration=measure,virtual_gauge_height_mm=height,
                max_incremental_support_residual_N=float(abs(residual[zero:]).max()),clamp_fit_check=pose_check,
                zero_load_reequilibration_max_sampled_translation_um=1000*float(abs(u[zero]-u[0]).max()),
                states=[dict(native_set=int(k+1),load_step=int(ls[k,0]),time=float(times[k]),applied_X_N=applied[j],
                    cell_centres_XYZ_um=(1000*centre_motion[j]).tolist(),left_to_clamps_XYZ_um=(1000*travel[j]).tolist(),
                    cell_roll=rotation_states[j],support_XYZ_N=reactions[j].tolist(),bolt_reactions_N=bolts[j].tolist()) for j,k in enumerate(steps)])
    if branch!='bare':
        from global_contact import pair_summary
        grid=raw.grid.cell_data;ids=grid['ansys_elem_num'][grid['ansys_etype']==853]
        assert len(ids)>0
        for i,s in zip(steps,result['states'],strict=True):
            num,vals,nn=raw.element_solution_data(int(i),'ECT')
            s['case_contact']=pair_summary(int(i),times[i],ids,num,vals,nn)
        from snug_locked_contact import contact_by_face, incremental_contact_forces, surface_owners
        mesh=MESH/'case_2.npz'
        verified(mesh,input_record(parent)['mesh_sha256'])
        owners=surface_owners(raw,mesh)
        by_face=contact_by_face(raw,owners,[s['case_contact'] for s in result['states']],steps)
        for s,faces in zip(result['states'],by_face,strict=True):
            assert s['native_set']==faces['native_set']
            s['loaded_case_faces']=faces['loaded_case_faces']
        # The original parent did not request MISC. The restart explicitly requests it.
        locked_middle = {e for patch in by_face[0]['loaded_case_faces'] if patch['STEP_face']==17
                         for e in patch['element_ids']}
        incremental_contact_forces(raw,owners,steps[zero:],result['states'][zero:],locked_middle)
        result['native_contact_scope']='Signed CNFX/Y/Z summed over every case contact face and target, referenced to the zero-added-load hold.'
        compare_pocket_unloading(branch,result,zero)
    prediction=AUDIT/f'{branch}_cell_flexibility.json'
    projected=read(prediction)
    assert projected['force_pattern_sha256']==spec['force_cards_sha256']
    stiffness=projected['cutoff_Hz']['4000']
    loading=[s for s in result['states'] if s['load_step'] in (4,5)]
    for s in loading:
        s['initial_tangent_left_cell_X_um']=s['applied_X_N']*stiffness['cell_X_compliance_um_per_N'][0][0]
        s['initial_tangent_left_to_clamps_X_um']=s['applied_X_N']*stiffness['left_relative_to_its_clamps_X_um_per_N']
    result['independent_flexibility_sha256']=digest(prediction)
    compare_full_tangent(branch,spec,result)
    result['scope']='Whole installed board loaded in +X through the mass-weighted nodes of its left cell. Displacements are relative to the zero-added-load hold; the original stage-2 lock is also retained for drift checks.'
    write_json(AUDIT/(case+'.json'),result)
    compare_closed()
    from snug_board_pull_stress import audit as check_stresses
    from snug_board_bond_forces import audit as check_bond_loads
    from snug_board_pull_work import audit as check_work
    check_work(branch)
    check_stresses(branch)
    check_bond_loads(branch)
    if branch != "bare":
        from snug_board_pull_seats import audit as check_mounts
        check_mounts(branch)


def compare_pocket_unloading(branch, result, zero):
    """Track the original pressure patch and its net force through loading and return."""
    record_path = AUDIT / f'{branch}_pocket_unloading.json'
    if not record_path.is_file():
        return
    record = read(record_path)
    assert record['branch'] == branch and record['load_order'][0] == 'left'
    tangent_path = AUDIT / f'{branch}_initial_cell_load_paths.json'
    verified(tangent_path, record['initial_load_paths_sha256'])
    tangent = read(tangent_path)
    full = AUDIT / f'{branch}_full_board_tangent.json'
    verified(full, tangent['full_tangent_sha256'])
    assert read(full)['static_rst_sha256'] == result['parent_rst_sha256']
    axis = np.asarray(record['opening_direction'])
    assert abs(np.linalg.norm(axis)-1) < 1e-12
    locked_faces = set(tangent['installed_contact_elements'])
    parent_patches = result['states'][0]['loaded_case_faces']
    assert locked_faces == {e for patch in parent_patches if patch['STEP_face']==17 for e in patch['element_ids']}
    slope = record['opening_force_increment_N_per_unit_positive_X_load'][0]
    preload = record['projected_compression_N'][record['selected_preload_source']]
    states = result['states'][zero:]
    assert states[0]['applied_X_N'] == 0
    held = np.dot(states[0]['native_middle_pocket_force']['CNF_XYZ_N'], axis)
    first_change = None
    for state in states:
        faces = {n for contact in state['loaded_case_faces'] if contact['STEP_face']==17 for n in contact['element_ids']}
        if faces != locked_faces and first_change is None:
            first_change = state['native_set']
        # Native CNF is force on the cell. Compression projects positively on
        # this axis, opposite to the signed compression force into the shell.
        projected = float(np.dot(state['native_middle_pocket_force']['CNF_XYZ_N'], axis))
        change = float(np.dot(state['native_middle_pocket_force']['change_from_zero_hold_XYZ_N'],axis))
        assert abs(projected-held-change) < 1e-8
        state['middle_patch_comparison'] = dict(original_closed_faces_retained=len(faces & locked_faces),
            new_closed_faces=len(faces - locked_faces), same_faces_as_parent=(faces==locked_faces),
            native_whole_case_projected_compression_N=projected, native_change_from_zero_hold_N=change,
            original_patch_tangent_projection_N=preload-slope*state['applied_X_N'])
    result['pocket_unloading_check'] = dict(prediction_sha256=digest(record_path),
        original_projected_compression_N=preload, zero_hold_native_projection_N=float(held),
        first_saved_set_with_different_faces=first_change,
        signed_left_cell_X_N_at_frozen_patch_zero=preload/slope,
        scope='The projection uses case-side STEP face 17. The separate assembly resultant includes all other case faces. '
              'The tangent refers to the original equilibrium; the native increments start at the converged zero-load hold.')

    sweep_path = AUDIT / f'{branch}_cellpush_swept_points.json'
    if sweep_path.is_file():
        sweep = read(sweep_path)
        assert sweep['parent_rst_sha256'] == result['parent_rst_sha256'] and sweep['whole_board_inputs_sha256'] == result['registry_sha256']
        assert {e for e,_ in sweep['original_bearing_points']} == locked_faces
        result['pocket_unloading_check']['swept_geometry_sha256'] = digest(sweep_path)

    released_path = AUDIT / f'{branch}_released_pocket_tangent.json'
    if released_path.is_file():
        release = read(released_path)
        assert release['installed_load_paths_sha256'] == digest(tangent_path)
        if 'single_contact_prediction' in release:
            compare_single_spring(result, states, release, released_path, record_path, held, preload, slope)


def compare_single_spring(result, states, release, released_path, record_path, held, preload, slope):
    """Test the one-point aluminium prediction at the actual native load stations."""
    path = release['single_contact_prediction']
    assert release['contact_rank'] == 1 and path['unloading_record_sha256'] == digest(record_path)
    seated = np.asarray(release['restored_compliance_X_um_per_N'])[:,0]
    opened = np.asarray(release['open_compliance_X_um_per_N'])[:,0]
    geometry = path['curved_cell_surfaces']
    confirmed_faces = {test['whole_shell']['witness']['case_contact_element']
                       for test in geometry.get('middle_surface_transition',{}).get('tests',[])
                       if 'case_contact_element' in test['whole_shell'].get('witness',{})}
    adjusted = held>0 and states[0]['middle_patch_comparison']['same_faces_as_parent']
    for state in states:
        force = state['applied_X_N']
        assert force>=0 and slope>0
        def prediction(offset):
            used = min(force, offset/slope)
            return seated*used + opened*(force-used)
        expected = prediction(preload)
        measured = np.asarray(state['cell_centres_XYZ_um'])[:,0]
        item = dict(predicted_centres_X_um=expected.tolist(),
                    native_minus_predicted_centres_X_um=(measured-expected).tolist())
        if adjusted:
            item['predicted_centres_using_native_hold_X_um']=prediction(held).tolist()
        if confirmed_faces:
            actual_faces = {n for group in state['loaded_case_faces'] for n in group['element_ids']}
            item['confirmed_geometric_faces_closed'] = sorted(confirmed_faces & actual_faces)
        state['single_spring_comparison'] = item
    result['single_spring_prediction_sha256'] = digest(released_path)


def compare_full_tangent(branch, spec, result):
    """Compare native load stations with the full tangent from the same installed board."""
    path=AUDIT/f'{branch}_full_board_tangent.json'
    if not path.is_file():
        return
    full=read(path)
    assert full['branch']==branch and full['static_rst_sha256']==result['parent_rst_sha256']
    assert full['force_cards_sha256']==spec['force_cards_sha256']
    centre_slope=np.array(full['cell_X_um_per_N'])[:,0]
    clamp_slope=full['left_relative_to_its_clamps_X_um_per_N'][0]
    for state in result['states']:
        if state['load_step']<4:
            continue
        force=state['applied_X_N']
        centres=np.asarray(state['cell_centres_XYZ_um'])[:,0]
        state['full_tangent_check']=dict(predicted_cell_centres_X_um=(force*centre_slope).tolist(),
            native_minus_predicted_cell_centres_X_um=(centres-force*centre_slope).tolist(),
            predicted_left_to_clamps_X_um=force*clamp_slope,
            native_minus_predicted_left_to_clamps_X_um=state['left_to_clamps_XYZ_um'][0]-force*clamp_slope)
    paths=AUDIT/f'{branch}_initial_cell_load_paths.json'
    if paths.is_file():
        recovery=read(paths)
        assert recovery['full_tangent_sha256']==digest(path)
        assert recovery['load_order']==['left','middle','right']
        # The test loads the left cell; its pocket is open initially. Board motion
        # can still shift the force at the middle pocket through the nickel strips.
        slope=np.asarray(recovery['cell_load_paths'][1]['case_XYZ_N_per_N'])[:,0]
        for state in result['states']:
            if state['load_step']>=4:
                state['full_tangent_check']['additional_middle_cell_force_into_PLA_XYZ_N']=(
                    state['applied_X_N']*slope).tolist()
        result['initial_load_paths_sha256']=digest(paths)
    result['full_linear_tangent_sha256']=digest(path)


def compare_closed():
    paths={branch:AUDIT/(branch+'_cellpush_x.json') for branch in BRANCHES}
    if not all(path.is_file() for path in paths.values()):
        return
    source={};comparisons={}
    specs=read(REGISTRY);identity=digest(REGISTRY)
    common=float(specs['bare_cellpush_x']['endpoint_force_N'])
    for branch,path in paths.items():
        data=read(path);name=branch+'_cellpush_x';entry=specs[name]
        assert data['case']==name and data['registry_sha256']==identity and data['parent_rst_sha256']==entry['parent_rst_sha256']
        assert entry['endpoint_force_N']==common and entry['force_cards_sha256']==specs['bare_cellpush_x']['force_cards_sha256']
        source[branch]=digest(path)
        for label,time,force in [('unit_load',4.,1.),('matched_load',5.,common),('unloaded',6.,0.)]:
            row,=[r for r in data['states'] if abs(r['time']-time)<1e-9]
            assert abs(row['applied_X_N']-force)<1e-9
            comparisons.setdefault(label,{})[branch]=dict(force_N=force,
                left_relative_to_its_clamps_X_um=row['left_to_clamps_XYZ_um'][0],
                left_middle_approach_X_um=row['cell_centres_XYZ_um'][0][0]-row['cell_centres_XYZ_um'][1][0],
                cell_centres_XYZ_um=row['cell_centres_XYZ_um'],loaded_case_STEP_faces=[
                    r['STEP_face'] for r in row.get('loaded_case_faces',[])])
    write_json(AUDIT/'whole_board_direct_comparison.json',dict(campaign=CAMPAIGN,inputs=source,
               registry_sha256=identity,direct_states=comparisons,
               scope='Nonlinear whole-board load endpoints after a zero-added-load hold. All cell motions are relative to that hold.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('stage','audit'));parser.add_argument('case',nargs='?')
    args=parser.parse_args()
    if args.action=='stage':stage()
    else:audit(args.case)

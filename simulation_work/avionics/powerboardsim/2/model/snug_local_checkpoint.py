"""Audit saved side-pull equilibria from a stationary, hash-verified copy while the parent job continues."""
import argparse
import re
from pathlib import Path

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT,read
from compare_pull import series
from film_identity import digest,verified,write_json
from global_contact import pair_summary
from installation_material import PLA,material_history
from local_equilibrium import SCREW_PILOTS,NEIGHBOR_PILOT,positions,recover
from partition_snapshot import converged_prefix,check_element_tables
from pull_pose_clearance import rigid_pose
from snug_directional_result import first_bracket,registered_gaps
from stage_snug_fit import AUDIT,INPUTS

CASE='snug125_nylon_lateral_friction_locked_pin1_m15'
CAMPAIGN='nov08_01'


def verify_capture(folder):
    capture=read(folder/'capture.json')
    case=capture['case']
    assert re.fullmatch(r'snug125_(nylon|aluminium)_lateral_friction_locked(_minus)?_pin1_m15',case)
    assert capture['campaign']==CAMPAIGN
    spec=read(AUDIT/'local_inputs_m15.json')[case]
    status=read(ROOT/'.runtime/receipts'/CAMPAIGN/case/'status.json')
    assert status['case']==case and spec['bare_reference']=='bare_'+spec['source']
    assert status['input_sha256'].lower()==spec['input_sha256'] and capture['source']==status['work']+'\\pull.rst'
    file=folder/'pull.rst'
    verified(file,capture['sha256']);assert file.stat().st_size==capture['bytes']
    verified(INPUTS/case/'model.inp',spec['input_sha256'])
    text=(folder/'solve.out').read_text(errors='replace')
    from snug_local_core_trial import verify_production_runtime
    job=INPUTS/case/'local_job.json'
    verified(job,spec['spec_sha256'])
    verify_production_runtime(case,CAMPAIGN,read(job),status,text)
    pattern=r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED[^\r\n]*[\r\n]+\s*\*\*\* TIME\s*=\s*([\d.Ee+\-]+)'
    events=list(re.finditer(pattern,text))
    steps=np.array([list(map(int,m.groups()[:2])) for m in events]);times=np.array([float(m[3]) for m in events])
    raw=reader.read_binary(str(file))
    assert len(steps)==raw.nsets and converged_prefix(raw,steps,times,False)==0
    check_element_tables(file,raw,len(steps))
    monitor=[line.split() for line in (folder/'pull.mntr').read_text().splitlines() if re.match(r'^\s*\d+\s+\d+\s+\d+\s',line)]
    last_monitor=capture['last_monitor']
    if isinstance(last_monitor,dict):
        last_monitor=last_monitor['value']
    assert last_monitor.split()==monitor[-1]
    assert np.array_equal(steps,[[int(line[0]),int(line[1])] for line in monitor])
    assert np.allclose(times,[float(x[6]) for x in monitor],rtol=0,atol=5.1e-5)
    return spec,capture,raw


def prepare_native_fields(folder,capture,raw,config,mesh):
    """Read only an identity-checked stationary copy using the installed DPF operators."""
    import fcntl,subprocess,sys
    from tab_seating import read_point_file
    source=folder/'pull.rst';sha=capture['sha256']
    sets=list(range(1,raw.nsets+1))
    supports=sorted({mesh['pilot'],*config['target_pilots'],*SCREW_PILOTS,NEIGHBOR_PILOT})
    faces=np.stack([e[10:18] for e in raw.mesh.elem if e[1]==862 and e[2]==861])
    points=sorted(set(supports).union(mesh['attachment'],map(int,faces.ravel())))
    read_point_file(source,folder/'dpf_points',sha,sets,points)
    out=folder/'dpf_forces';out.mkdir(exist_ok=True)
    with (out/'request.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        spec=dict(source_sha256=sha,nodes=supports,sets=sets)
        request=out/'request.json'
        if request.exists():assert read(request)==spec
        else:write_json(request,spec)
        if not (out/'forces.json').exists():
            if (out/'dispatch.json').exists():
                raise RuntimeError('Reconcile the existing DPF reaction readback before dispatch')
            driver=ROOT/'model/dpf_support_forces.py'
            def win(path):return chr(92)*2+'Mac'+chr(92)+'Home'+chr(92)+str(path.relative_to('/Users/mdn')).replace('/',chr(92))
            exe=r'C:\Program Files\ANSYS Inc\v261\commonfiles\IronPython\ipy64.exe'
            cmd="& '{}' '{}' '{}' '{}'\nexit $LASTEXITCODE".format(exe,win(driver),win(source),win(out))
            write_json(out/'dispatch.json',dict(source_sha256=sha,reader_sha256=digest(driver)))
            result=subprocess.run([sys.executable,str(ROOT/'model/guest_command.py'),'--timeout','3600'],
                                  input=cmd,text=True,capture_output=True)
            (out/'export.log').write_text(result.stdout+result.stderr)
            assert result.returncode==0 and 'DPF_SUPPORT_FORCES_DONE' in result.stdout


def movements(folder,capture,raw,settings,mesh):
    out=folder/'dpf_points';req=read(out/'request.json');done=read(out/'done.json')
    assert req['source_sha256']==done['source_sha256']==capture['sha256']
    assert req['sets']==done['sets']==list(range(1,raw.nsets+1))
    ids=np.asarray(req['nodes']);assert done['nodes']==len(ids) and done['unit'].lower()=='mm'
    u=np.fromfile(out/'displacements.bin','<f8').reshape(raw.nsets,len(ids),3)
    assert np.isfinite(u).all()
    assert np.all(np.diff(ids)>0)
    pilot=mesh['pilot'];attached=np.asarray(mesh['attachment']);bottom=settings['bottom_pilots']
    initial=raw.mesh.nodes[positions(raw.mesh.nnum,attached)]
    coords=raw.mesh.nodes[positions(raw.mesh.nnum,[pilot])[0]]
    where=positions(ids,attached);index=positions(ids,[pilot])[0]
    error=0.;resid=0.
    for k,field in enumerate(u):
        _,shift,delta=rigid_pose(initial,initial+field[where],coords)
        error=max(error,float(abs(shift-field[index]).max()));resid=max(resid,delta)
    assert error<2e-6 and resid<1e-5,(error,resid)
    expected=settings['sign']*settings['displacement_mm']*np.clip(raw.time_values-settings['pull_start_time'],0,1)
    assert np.max(abs(u[:,index,0]-expected))<1e-7
    assert np.max(abs(u[:,positions(ids,[*SCREW_PILOTS,NEIGHBOR_PILOT])]))<1e-7
    held=raw.time_values>=settings['pull_start_time']
    assert np.max(np.ptp(u[held][:,positions(ids,bottom),:],axis=0))<1e-7
    moving={ (k+1,n):u[k,i] for n,i in zip([pilot,*bottom],positions(ids,[pilot,*bottom]),strict=True)
            for k in range(raw.nsets) }
    return moving,dict(rigid_attachment_nodes=len(attached),maximum_rigid_pose_residual_mm=resid,
                       maximum_DPF_pilot_vs_fitted_shift_mm=error,DPF_translations_sha256=digest(out/'displacements.bin'))


def force_balance(folder,capture,raw,config,source,moving):
    rows=recover(folder/'pull.rst',source,moving,True)
    out=folder/'dpf_forces';data=read(out/'forces.json');spec=read(out/'request.json')
    assert data['source_sha256']==spec['source_sha256']==capture['sha256']
    assert spec['sets']==list(range(1,raw.nsets+1))
    assert set(spec['nodes'])=={read(source/'mesh.json')['pilot'],*config['target_pilots'],*SCREW_PILOTS,NEIGHBOR_PILOT}
    assert len(rows)==len(data['sets'])==raw.nsets
    mx=0.;max_fx=0.;max_y=0.;max_z=0.;max_m=0.
    for k,(br,dpf) in enumerate(zip(rows,data['sets'],strict=True)):
        assert br['native_set']==dpf['native_set']==k+1
        forces,ns,dofs=raw.nodal_reaction_forces(k)
        for n in spec['nodes']:
            hit=(ns==n)&(dofs<=3)
            v=np.bincount(dofs[hit]-1,weights=forces[hit],minlength=3)
            value=np.asarray(dpf['forces_N'].get(str(n),[0.]*3))
            mx=max(mx,float(abs(v-value).max()))
        assert abs(br['cell_fx_N']-dpf['forces_N']['2481'][0])<1e-4
        if np.isclose(br['time'],config['pull_start_time']):
            assert all(abs(abs(dpf['forces_N'][str(n)][2])-config['preload_N'])<.1 for n in config['bottom_pilots'])
        max_fx=max(max_fx,abs(br['force_N_x'])/max(1.,abs(br['cell_fx_N'])))
        max_y=max(max_y,abs(br['force_N_y']));max_z=max(max_z,abs(br['force_N_z']))
        if br['loadstep']==3:
            moment=np.linalg.norm([br['moment_cell_Nmm_'+a] for a in 'xyz'])
            max_m=max(max_m,moment/max(1.,abs(br['cell_fx_N'])*42.5))
    assert mx<1e-4 and max_fx<.01 and max_y<.1 and max_z<.2 and max_m<.01,(mx,max_fx,max_y,max_z,max_m)
    return rows,dict(maximum_DPF_vs_RST_force_component_N=mx,maximum_relative_X_imbalance=max_fx,
                     maximum_Y_imbalance_N=max_y,maximum_Z_imbalance_N=max_z,maximum_relative_pull_moment_residual=max_m,
                     DPF_reaction_sha256=digest(out/'forces.json'))


def contact_history(raw,rows):
    g=raw.grid.cell_data
    groups={rid:g['ansys_elem_num'][(g['ansys_etype']==862)&(g['ansys_real_constant']==rid)] for rid in (861,862)}
    assert all(len(v)>0 for v in groups.values())
    contact=[]
    for k,br in enumerate(rows):
        enum,values,_=raw.element_solution_data(k,'EMN')
        ee,ect,nodes=raw.element_solution_data(k,'ECT')
        both={}
        for rid,elements in groups.items():
            idx=np.searchsorted(enum,elements);assert np.array_equal(enum[idx],elements)
            items=[values[i] for i in idx if values[i] is not None and len(values[i])]
            a=np.stack(items) if items else np.empty((0,45));assert a.shape[1]>=45
            corners=pair_summary(k,br['time'],elements,ee,ect,nodes)
            loaded=a[:,:4]>=2
            closed=int((a[:,40]>=2).sum())
            assert corners['sliding']+corners['sticking']==loaded.any(axis=1).sum()
            pen=float(a[:,8:12][loaded].max(initial=0.))
            assert np.isclose(pen,corners['loaded_corner_pen_max'],atol=1e-9,rtol=2.e-6)
            f=a[:,42:45].sum(axis=0,dtype=float)
            if br['loadstep']<=2:assert closed==0 and abs(f).max()<1e-4
            if rid==861:
                support=np.array([br['screw_support_N_'+x]+br['neighbor_support_N_'+x] for x in 'xyz'])
                assert np.linalg.norm(f-support)<=max(.01,.002*np.linalg.norm(f))
            both[str(rid)]=dict(closed_faces=closed,loaded_corners=int(loaded.sum()),max_loaded_penetration_mm=pen,
                                force_N=f.tolist())
        contact.append(both)
    return contact


def audit(folder):
    spec,capture,raw=verify_capture(folder)
    case=capture['case']
    source=ROOT/'.runtime/local_inputs'/spec['source']
    catalog=read(ROOT/'validation/local_inputs.json')[source.name]['files']
    for name in ('mesh.json','config.json','model.inp'):verified(source/name,catalog[name])
    config=read(source/'config.json'); mesh=read(source/'mesh.json')
    sign=config['sign']
    assert sign==(-1 if source.name.endswith('_minus') else 1)
    prepare_native_fields(folder,capture,raw,config,mesh)
    moving,pose=movements(folder,capture,raw,config,mesh)
    rows,balance=force_balance(folder,capture,raw,config,source,moving)
    print('Balance passed',len(rows),flush=True)
    contacts=contact_history(raw,rows)
    print('Both contact pairs passed',flush=True)
    forces=np.array([r['cell_fx_N'] for r in rows]);travel=np.array([r['ux_mm'] for r in rows])
    deck=(INPUTS/case/'model.inp').read_text()
    nt,history,first,serr,berr,axerr=material_history(raw,deck,np.arange(len(rows)),travel,local=True,forces=forces)
    assert nt==read(AUDIT/'local_mesh15_preflight.json')['native_counts']['tetrahedra']
    baseline,bare=series(spec['bare_reference'])
    assert baseline['source']==spec['source']==source.name and baseline['campaign']==CAMPAIGN
    measurements=[];eligible=[];stop=None;touch=None
    for k,(br,contact,mat) in enumerate(zip(rows,contacts,history,strict=True)):
        assert br['native_set']==mat['native_set']==k+1
        ratios={metric:mat['all_'+metric]/limit for metric,limit in PLA.items()}
        max_pen=max(c['max_loaded_penetration_mm'] for c in contact.values())
        if stop is None and (max(ratios.values())>=1 or max_pen>.05):stop=k+1
        if contact['861']['closed_faces']>0 and touch is None:
            touch=[dict(native_set=j+1,travel_mm=rows[j]['ux_mm'],cell_force_N=rows[j]['cell_fx_N']) for j in (k-1,k)]
        row=dict(native_set=k+1,loadstep=br['loadstep'],substep=br['substep'],travel_mm=br['ux_mm'],cell_force_N=br['cell_fx_N'],
                 screw_support_resistance_N=-br['screw_support_N_x'],neighbor_resistance_N=-br['neighbor_support_N_x'],
                 nickel_clamp_resistance_N=br['cell_fx_N']+br['screw_support_N_x']+br['neighbor_support_N_x']-br['force_N_x'],
                 printed_coupon_percent={key:100*v for key,v in ratios.items()},screw_peak_fibre_MPa=max(mat['four_screws']['peak_fiber_tension_MPa']),
                 both_contact_pairs=contact,within_screens=stop is None)
        measurements.append(row)
        if stop is None and br['time']>=config['pull_start_time']:
            eligible.append(dict(set=k+1,ux_mm=br['ux_mm'],cell_force_N=br['cell_fx_N']))
    assert sign*bare[-1]['ux_mm']>0 and sign*bare[-1]['cell_force_N']>0
    equal_load=first_bracket(eligible,'cell_force_N',bare[-1]['cell_force_N'],sign)
    last_common=None
    if eligible and sign*eligible[-1]['ux_mm']>1e-9:
        last=eligible[-1]
        bare_at=first_bracket(bare,'ux_mm',last['ux_mm'],sign)
        assert bare_at is not None
        last_common=dict(cased=last,bare=bare_at)
    result=dict(case=case,campaign=CAMPAIGN,completed=False,checkpoint=folder.name,
                rst_sha256=capture['sha256'],result_bytes=capture['bytes'],input_sha256=spec['input_sha256'],
                listing_sha256=digest(folder/'solve.out'),monitor_sha256=digest(folder/'pull.mntr'),capture_sha256=digest(folder/'capture.json'),
                converged_sets=raw.nsets,final_converged_loadstep_substep=raw._resultheader['ls_table'][-1,:2].tolist(),
                pose_check=pose,equilibrium=balance,case_tetrahedra=nt,constitutive_errors=dict(PLA=serr,beam=berr,beam_area=axerr),
                states=measurements,first_print_crossings=first,first_excluded_set=stop,first_loaded_moving_cell_bracket=touch,
                equal_bare_endpoint_load=dict(bare=bare[-1],cased=equal_load),last_common_travel=last_common,
                scope='Verified stationary copy of completed MAPDL increments during the ongoing lateral pull. This record '
                      'does not release the solver job or its dependencies. Comparisons stop at the first printed-material '
                      'reference crossing or 0.05 mm loaded-corner penetration screen. Forces are for the prescribed fixture.')
    result['DPF_files']={name:digest(folder/name) for name in ('dpf_forces/request.json','dpf_points/request.json',
                         'dpf_points/done.json','dpf_points/dispatch.json')}
    result['bare_case']=spec['bare_reference']
    result['bare_rst_sha256']=baseline['rst_sha256']
    result['initial_contact_search']=registered_gaps(folder,{'solve.out':result['listing_sha256'],
                                            'pull.rst':capture['sha256']},spec,'1.5')
    destination=AUDIT/(case+'_'+folder.name+'_checkpoint.json')
    if destination.exists():
        assert read(destination)==result, 'Checkpoint differs from its existing audit'
    else:
        write_json(destination,result)
    print('Last matched travel',result['last_common_travel'],'equal load',equal_load,'contact',touch,flush=True)


def audit_terminal(folder):
    """Check the original process exit and RST set inventory before POST1 publishes a partial verdict."""
    from datetime import datetime
    from snug_local_core_trial import verify_production_runtime
    stamp = read(folder/'capture.json')
    assert stamp['case'] == CASE and stamp['campaign'] == CAMPAIGN
    receipt = ROOT/'.runtime/receipts'/CAMPAIGN/CASE
    source = ROOT/'.runtime/local_inputs/lateral_friction_locked'
    spec = read(AUDIT/'local_inputs_m15.json')[CASE]
    verified(receipt/'observed_solver_exit.json',stamp['exit_sha256'].lower())
    exit_record = read(receipt/'observed_solver_exit.json')
    status = read(receipt/'status.json')
    assert exit_record['case'] == status['case'] == CASE and exit_record['exit_code'] != 0
    assert exit_record['input_sha256'] == status['input_sha256'].lower() == spec['input_sha256']
    assert stamp['source'] == status['work'] + chr(92) + 'pull.rst'
    path = folder/'pull.rst'
    verified(path, stamp['rst_sha256'])
    assert stamp['bytes'] == path.stat().st_size
    verified(folder/'solve.out', stamp['listing_sha256'].lower())
    verified(folder/'pull.mntr', stamp['monitor_sha256'].lower())
    verified(INPUTS/CASE/'local_job.json',spec['spec_sha256'])
    verified(INPUTS/CASE/'model.inp',spec['input_sha256'])
    listing = (folder/'solve.out').read_text(errors='replace')
    assert re.search(r'REASON FOR TERMINATION[^\n]*UNCONVERGED SOLUTION',listing) and 'RUN COMPLETED' in listing
    cores = verify_production_runtime(CASE,CAMPAIGN,read(INPUTS/CASE/'local_job.json'),status,listing)
    pattern = r'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED[^\r\n]*[\r\n]+\s*\*\*\* TIME\s*=\s*([\d.Ee+\-]+)'
    events = re.findall(pattern,listing)
    steps = np.array([[int(ls),int(ss)] for ls,ss,_ in events])
    times = np.array([float(t) for _,_,t in events])
    raw = reader.read_binary(str(path))
    terminal = converged_prefix(raw,steps,times,True)
    assert terminal == 1
    check_element_tables(path,raw,len(steps))
    monitor = [line.split() for line in (folder/'pull.mntr').read_text().splitlines()
               if re.match(r'^\s*\d+\s+\d+\s+\d+\s+',line)]
    assert np.array_equal(steps,[[int(row[0]),int(row[1])] for row in monitor])
    np.testing.assert_allclose(raw.time_values[:len(steps)],[float(row[6]) for row in monitor],rtol=0,atol=5.1e-5)
    pilot = read(source/'mesh.json')['pilot']
    cfg = read(source/'config.json')
    prefix_files = sorted(AUDIT.glob(CASE+'_ls*_checkpoint.json'))
    assert prefix_files
    checks = []
    force = []
    travel = cfg['sign']*cfg['displacement_mm']*np.clip(raw.time_values[:len(steps)]-cfg['pull_start_time'],0,1)
    for i in range(len(steps)):
        values, ids, dofs = raw.nodal_reaction_forces(i)
        force.append(float(values[(ids==pilot)&(dofs==1)].sum()))
    for check in prefix_files:
        known=read(check)
        assert known['case']==CASE and known['input_sha256']==spec['input_sha256'] and not known['completed']
        n=known['converged_sets']
        np.testing.assert_allclose(force[:n],[r['cell_force_N'] for r in known['states']],rtol=1e-7,atol=1e-5)
        np.testing.assert_allclose(travel[:n],[r['travel_mm'] for r in known['states']],rtol=0,atol=1e-7)
        assert np.array_equal(steps[:n],[[r['loadstep'],r['substep']] for r in known['states']])
        checks.append(dict(checkpoint=check.name,sha256=digest(check),matching_states=n))
    elapsed=(datetime.fromisoformat(exit_record['exit_utc'])-datetime.fromisoformat(exit_record['native_start_utc'])).total_seconds()
    # The original moving-support POST1 closed before the replacement table readback.
    # Apply the existing fixture tolerances to each physical reaction set.
    from local_equilibrium import movement_table
    moving = folder/'moving_supports.csv'
    moving_log = folder/'moving.out'
    assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',moving_log.read_text(errors='replace'))
    balance = recover(path,source,movement_table(moving),True)
    assert len(balance) == len(steps)
    failed = []
    for row,expected_force,expected_ux in zip(balance,force,travel,strict=True):
        assert abs(row['ux_mm']-expected_ux)<1e-7 and abs(row['cell_fx_N']-expected_force)<1e-5
        x,y,z = (row['force_N_'+ax] for ax in 'xyz')
        moment = np.linalg.norm([row['moment_cell_Nmm_'+ax] for ax in 'xyz'])
        scale = max(1,abs(expected_force))
        rel_moment = moment/max(1,abs(expected_force)*42.5)
        if abs(x)/scale >= .01 or abs(y) >= .1 or abs(z) >= .2 or (row['loadstep']>=3 and rel_moment>=.01):
            failed.append(dict(native_set=row['native_set'],travel_mm=row['ux_mm'],force_residual_N=[x,y,z],
                               relative_lateral_imbalance=abs(x)/scale,relative_pull_moment=rel_moment))
    prefix=failed[0]['native_set']-1 if failed else len(balance)
    record=dict(case=CASE,campaign=CAMPAIGN,input_sha256=spec['input_sha256'],observed_exit_sha256=stamp['exit_sha256'].lower(),
                original_exit=exit_record['exit_code'],solver_wall_seconds=elapsed,rst_sha256=stamp['rst_sha256'],result_bytes=stamp['bytes'],
                listing_sha256=stamp['listing_sha256'].lower(),monitor_sha256=stamp['monitor_sha256'].lower(),runtime=cores,
                RST_sets=raw.nsets,converged_states=len(steps),last_converged_step=steps[-1].tolist(),
                original_moving_supports_sha256=digest(moving),moving_listing_sha256=digest(moving_log),
                force_balance_violations=failed,first_contiguous_balance_pass_states=prefix,
                last_travel_before_balance_violation_mm=balance[prefix-1]['ux_mm'] if prefix else None,
                last_converged_time=float(raw.time_values[len(steps)-1]),last_imposed_travel_mm=float(travel[-1]),
                excluded_terminal_set=raw._resultheader['ls_table'][-1,:2].tolist(),matching_checkpoints=checks,
                scope='Closed original native file and solver-exit inventory. The failed terminal state is excluded. '
                      'This verifies saved set identities and earlier force and travel histories; material and complete fixture audits retain their own scope.')
    write_json(AUDIT/(CASE+'_termination.json'),record)
    print(len(steps),steps[-1],travel[-1],elapsed,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path)
    p.add_argument('--terminal',action='store_true',help='Use the closed result with its original observed structural exit.')
    args=p.parse_args()
    (audit_terminal if args.terminal else audit)(args.folder.resolve())

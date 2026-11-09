"""Compare the four sealed contact replay loads with their native parent and locate earlier cell encounters."""
import numpy as np
from audit_local import ROOT,read
from audit_motion import selected_native_coordinates
from case_stress import source
from contact_patch import BRANCH,local_fields
from early_cell_clearance import bezier,subdivision_weights
from film_cell_contact import series
from film_cell_timestep import intervals,resolve_cells
from film_identity import digest,verified,write_json
from seeded_motion import FS


def boundary_history(folder,spec,state,q,samples,base_acceleration):
    for name,sha in spec['files'].items():
        verified(folder/name,sha)
    stride=spec['stride']
    stations=np.arange(0,len(samples),stride)
    assert len(stations)==spec['samples'] and stations[-1]==samples[-1]
    times=np.loadtxt(folder/'pbt.dat')-1
    assert np.array_equal(times,stations/FS) and times[-1]==spec['last_physical_time_s']
    drive=np.loadtxt(folder/'pba.dat')
    assert np.allclose(drive,base_acceleration[stations],rtol=1.e-11,atol=1.e-10)
    nodes=np.loadtxt(folder/'pbn.dat',dtype=float).astype(int)
    assert np.array_equal(nodes,state['driven'])
    ids=np.searchsorted(state['nodes'],nodes)
    coeff=np.loadtxt(folder/'pbq.dat').reshape(len(stations),q.shape[1]+1,order='F')
    assert np.all(coeff[:,0]==1)
    matrices=[]
    for j,axis in enumerate('xyz'):
        u=np.loadtxt(folder/f'shape{axis}.dat').reshape(q.shape[1]+1,len(ids),order='F')
        assert np.allclose(u[0],state['locked'][ids,j],rtol=1.e-13,atol=1.e-17)
        assert np.allclose(u[1:].T,state['phi'][ids,j],rtol=1.e-13,atol=1.e-17)
        matrices.append(u[1:])
    # The static terms coincide and cancel in the difference. APDL interpolates the dynamic tables in time.
    knots=coeff[:,1:]
    interpolated=np.column_stack([np.interp(samples,stations,column) for column in knots.T])
    shape=np.stack(matrices,axis=2).reshape(q.shape[1],-1)
    worst=0.;knot_max=0.;error2=0.;norm2=0.;max_sample=0;max_node=0
    for start in range(0,len(samples),64):
        sl=slice(start,start+64)
        native=q[sl]@shape
        delta=(interpolated[sl]-q[sl])@shape
        errors=np.linalg.norm(delta.reshape(len(native),len(nodes),3),axis=2)
        where=np.unravel_index(errors.argmax(),errors.shape)
        if errors[where]>worst:
            max_sample=start+int(where[0]);max_node=int(nodes[where[1]]);worst=float(errors[where])
        knot_max=max(knot_max,float(errors[samples[sl]%stride==0].max(initial=0)))
        norm2+=np.einsum('ij,ij->',native,native)
        error2+=np.einsum('ij,ij->',delta,delta)
    assert knot_max<2.e-8
    return dict(samples=len(samples),table_stations=len(times),driven_nodes=len(nodes),native_step_s=1/FS,
                table_step_s=stride/FS,max_table_station_difference_um=knot_max*1.e6,
                max_interpolated_displacement_difference_um=worst*1.e6,worst_node=max_node,worst_time_s=max_sample/FS,
                interpolated_dynamic_field_relative_L2=float(np.sqrt(error2/norm2)),
                maximum_interpolated_base_acceleration_error_m_s2=float(np.max(abs(np.interp(samples,stations,drive)-base_acceleration))))


def patch_history(state,q,samples):
    nodes=state['nodes']
    base=(state['xyz']+state['locked'])*1000
    movement=np.moveaxis(state['phi']*1000,2,0)
    surfaces={mat:np.stack([v for _,v in info[1]]) for mat,info in state['bodies'].items()}
    cell_ids=np.unique(np.concatenate([surfaces[k].ravel() for k in (187,191)]))
    movement=movement-movement[:,np.searchsorted(nodes,cell_ids)].mean(axis=1,keepdims=True)
    indices={k:np.searchsorted(nodes,faces) for k,faces in surfaces.items()}
    assert all(np.array_equal(nodes[v],surfaces[k]) for k,v in indices.items())
    rest={k:bezier(base[v]) for k,v in indices.items()}
    modes={k:bezier(movement[:,v,:]) for k,v in indices.items()}
    output={}
    for mat,name in [(191,'centre'),(187,'right')]:
        states,count,depths=series([rest[850],rest[mat]],[modes[850],modes[mat]],q,subdivision_weights())
        states=np.asarray(states)
        output[name]=dict(crossing_intervals_samples=intervals(samples[states=='intersecting']),
                          unresolved_intervals_samples=intervals(samples[states=='unresolved']),
                          intersecting_samples=len(depths),quadratic_faces=len(rest[mat]),candidate_pairs=count)
    return output


def run(campaign):
    basis=BRANCH+'_basis'
    modal,_,rst=source(basis,campaign)
    motion_path=ROOT/'validation/motion'/f'{BRANCH}_motion_X.json'
    motion=read(motion_path)
    replay_path=ROOT/'validation/contact_replay_inputs.json';replays=read(replay_path)
    wave_path=ROOT/'validation/patch_waveform.json';wave=read(wave_path)
    assert motion['campaign']==wave['campaign']==campaign
    assert motion['basis_rst_sha256']==modal['rst_sha256']==wave['global_basis_sha256']
    mcf=ROOT/'.runtime/archive'/campaign/motion['case']/'file.mcf'
    verified(mcf,motion['mcf_sha256'])
    samples=np.arange(wave['replay_last_index']+1)
    q=selected_native_coordinates(mcf,rst.time_values,samples)
    assert np.all(q[0]==0) and samples[-1]/FS==wave['replay_last_time_s']
    load=ROOT/'.runtime/motion_loads/X.txt'
    verified(load,motion['input_sha256'])
    acceleration=np.loadtxt(load,skiprows=1,max_rows=len(samples))
    assert np.allclose(acceleration[:,0],samples/FS,rtol=0,atol=5.1e-13)
    controls=read(ROOT/'validation/film_cell_contact'/f'{BRANCH}.json')
    assert controls['basis_sha256']==modal['rst_sha256'] and controls['campaign']==campaign
    full,states=resolve_cells(BRANCH,campaign,rst,modal,q,samples,controls['quadratic_faces'])
    assert states[0]=='separated'
    boundary={};domains={}
    for radius in (9,15):
        state=local_fields(campaign,radius)
        assert state['native_basis']==modal['rst_sha256']
        domains[radius]=patch_history(state,q,samples)
        for case,spec in replays.items():
            if spec['radius_mm']!=radius: continue
            assert spec['case']==case and spec['campaign']==campaign and spec['branch']==BRANCH
            assert spec['global_basis_sha256']==state['native_basis'] and spec['global_static_sha256']==state['native_static']
            boundary[case]=boundary_history(ROOT/'.runtime/inputs'/case,spec,state,q,samples,acceleration[:,1])
        print(radius,domains[radius],flush=True)
    assert len(boundary)==len(replays)==4
    write_json(ROOT/'validation/contact_replay_parent.json',dict(campaign=campaign,branch=BRANCH,base_axis='X',
        native_motion_sha256=digest(motion_path),native_mcf_sha256=motion['mcf_sha256'],basis_sha256=modal['rst_sha256'],
        acceleration_sha256=motion['input_sha256'],replay_inputs_sha256=digest(replay_path),prior_search_sha256=digest(wave_path),
        samples=len(samples),sampling_Hz=FS,full_cells=full,patch_cells=domains,boundary_tables=boundary,
        scope='Native open-contact parent response at all integration stations from rest through the prescribed '
              'replay interval. The full cell skins and the two restricted patch geometries are examined separately. '
              'The four sealed replay tables are compared with the parent. Local nonlinear contact solutions have their own audit.'))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign',default='nov08_01')
    run(p.parse_args().campaign)

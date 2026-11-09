"""Measure energy stored in the printed enclosure and its four elastic shanks during a raised side pull."""
import argparse
import re

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT,read,table
from compare_pull import series
from film_identity import digest,verified,write_json
from local_equilibrium import positions
from tab_seating import point_fields


def skew_arm(arm):
    x,y,z=arm.T
    zero=np.zeros(len(x))
    return np.stack((zero,z,-y,-z,zero,x,y,-x,zero),axis=1).reshape(-1,3,3)


def recover(case,campaign):
    proof,path=series(case)
    assert case in ('stand3_nylon_lateral_friction_locked_pin1','stand3_aluminium_lateral_friction_locked_pin1')
    assert campaign==proof['campaign']
    folder=ROOT/'.runtime/archive'/campaign/case
    ledger=read(ROOT/'.runtime/receipts'/campaign/case/'archived.json')
    hashes={r['name']:r['sha256'] for r in ledger['files']}
    assert ledger['case']==case and ledger['campaign']==campaign and proof['rst_sha256']==hashes['pull.rst']
    verified(folder/'pull.rst',hashes['pull.rst']);verified(folder/'model.inp',hashes['model.inp'])
    material=read(ROOT/'validation/pull_material'/(case+'.json'))
    assert material['rst_sha256']==hashes['pull.rst']
    r=reader.read_binary(str(folder/'pull.rst'));g=r.grid.cell_data
    mesh=r.mesh.elem;order=np.argsort(r.mesh.enum)
    def geometry(etype):
        ids=np.sort(g['ansys_elem_num'][g['ansys_etype']==etype])
        ix=order[np.searchsorted(r.mesh.enum[order],ids)]
        assert np.array_equal(r.mesh.enum[ix],ids)
        return ids,np.stack([mesh[j][10:] for j in ix])
    tet,tet_nodes=geometry(850);beam,beam_nodes=geometry(851)
    beam_ends=beam_nodes[:,:2]
    assert len(tet)==material['case_tets'] and tet_nodes.shape==(len(tet),10)
    assert np.array_equal(beam_ends,np.arange(950001,950009).reshape(4,2))
    sets=np.flatnonzero(r._resultheader['ls_table'][:,1]!=999999)+1
    points,disp=point_fields(r,sets,np.r_[np.unique(tet_nodes),beam_ends.ravel()],field_directory='pull_case_energy')
    beam_index=positions(points,beam_ends);solid_index=positions(points,tet_nodes).ravel()
    # CERIG sets each original bearing-node translation to u_pilot + rotation x arm.
    # This provides the rotational work at the physical end of each beam from
    # the independently recovered displacements, including its bending moment.
    deck=(folder/'model.inp').read_text()
    six=np.zeros((len(sets),4,2,6));six[:,:,:,:3]=disp[:,beam_index]
    max_ring_error=0.
    collars=[]
    for i,(lower,upper) in enumerate(beam_ends):
        ids=np.array([int(j) for j in re.findall(r'(?im)^CERIG,'+str(lower)+r',(\d+),UXYZ',deck)])
        assert len(ids)>=3 and np.unique(ids).size==len(ids) and f'D,{upper},ALL,0' in deck
        coords=r.mesh.nodes[positions(r.mesh.nnum,ids)]
        arm=coords-r.mesh.nodes[positions(r.mesh.nnum,[lower])][0]
        collars.append((positions(points,ids),arm))
        matrix=skew_arm(arm).reshape(-1,3);assert np.linalg.matrix_rank(matrix)==3
        delta=disp[:,positions(points,ids)]-disp[:,beam_index[i,0],None,:]
        rot=np.linalg.lstsq(matrix,delta.reshape(len(sets),-1).T,rcond=None)[0].T
        error=abs(rot@matrix.T-delta.reshape(len(sets),-1)).max()
        assert error<1e-6,error
        max_ring_error=max(max_ring_error,float(error))
        six[:,i,0,3:]=rot
        assert abs(six[:,i,1]).max()<1e-9
    groups=[tet,beam];energy=[];work=np.zeros(2);hist=[]
    springs,pad_nodes=geometry(854)
    assert np.array_equal(pad_nodes,beam_ends)
    mounts=[];support_error=0.;collar_force_error=collar_moment_error=0.
    previous=None;internal_fraction=0.
    for it,k in enumerate(sets):
        numbers,fields,_=r.element_solution_data(int(k-1),'ENG')
        sums=[]
        for ids in groups:
            ix=positions(numbers,ids);vec=np.stack([fields[j] for j in ix])
            assert vec.shape==(len(ids),11) and np.isfinite(vec[:,:4]).all() and np.all(vec[:,0]>0)
            assert abs(vec[:,2:4]).max()<1e-11
            sums.append(float(vec[:,1].sum(dtype=np.float64)))
        enum,values,_=r.element_solution_data(int(k-1),'ENF')
        sf=np.stack([values[j] for j in positions(enum,tet)]).reshape(-1,3)
        bf=np.stack([values[j] for j in positions(enum,beam)]).reshape(4,-1,6)
        # The higher-order beam has internal solution nodes. Their equilibrated
        # residual is checked against the physical end forces at each saved state.
        ratio=float(np.max(abs(bf[:,2:]),initial=0)/max(1.,np.max(abs(bf[:,:2]))))
        pad=np.zeros((4,3))
        for i,j in enumerate(positions(enum,springs)):
            if values[j] is not None and len(values[j]):
                pad[i]=values[j].reshape(2,3)[1]
        reaction,number,dof=r.nodal_reaction_forces(int(k-1))
        fixed=np.zeros((4,6))
        for i,node in enumerate(beam_ends[:,1]):
            use=number==node
            np.add.at(fixed[i],dof[use]-1,reaction[use])
        # Upper pilots carry the screw beam and a compression-only tab seat.
        err=fixed+bf[:,1,:]
        err[:,:3]+=pad
        assert np.allclose(err,0,rtol=0,atol=1e-3),(k,err)
        support_error=max(support_error,float(np.abs(err).max()))
        data=[]
        for i,node in enumerate(beam_ends[:,1]):
            data.append(dict(pilot=int(node),support_XYZ_N=fixed[i,:3].tolist(),
                    support_moment_XYZ_Nmm=fixed[i,3:].tolist(),seat_contribution_XYZ_N=(-pad[i]).tolist(),
                    beam_energy_mJ=float(vec[i,1])))
        mounts.append(data)
        internal_fraction=max(internal_fraction,ratio)
        assert ratio<1e-5
        assembled=np.zeros((len(points),3));np.add.at(assembled,solid_index,sf)
        for i,(ind,arm) in enumerate(collars):
            # The bearing tie uses reference arms in its constraint equations.
            # Test the corresponding force and moment independently on both sides.
            force=-assembled[ind].sum(0)
            moment=-np.cross(arm,assembled[ind]).sum(0)
            ferr=float(abs(force-bf[i,0,:3]+pad[i]).max())
            merr=float(abs(moment-bf[i,0,3:]).max())
            assert ferr<.002 and merr<.002,(k,i,ferr,merr)
            collar_force_error=max(collar_force_error,ferr);collar_moment_error=max(collar_moment_error,merr)
            mounts[-1][i].update(PLA_bearing_pilot=int(beam_ends[i,0]),reference_position_mm=
                    r.mesh.nodes[positions(r.mesh.nnum,[beam_ends[i,0]])][0].tolist(),
                    force_on_PLA_XYZ_N=force.tolist(),moment_on_PLA_XYZ_Nmm=moment.tolist())
        cur=(assembled,bf[:,:2].astype(float))
        if previous is not None:
            for j,u in enumerate((disp,six)):
                work[j]-=float(np.sum((previous[j]+cur[j])*.5*(u[it]-u[it-1])))
        previous=cur
        energy.append(sums);hist.append(work.copy())
    energy=np.array(energy);hist=np.array(hist)
    times=np.array([a['set']-1 for a in path])
    assert np.array_equal(sets[times],times+1)
    gain=energy[times]-energy[times[0]]
    direct=hist[times]-hist[times[0]]
    discrepancy=abs(direct-gain).max(0)/np.maximum(gain.max(0),1.e-12)
    print(case,'last native',gain[-1],'integrated',direct[-1],'relative path errors',discrepancy,flush=True)
    assert np.max(discrepancy)<.02
    x=np.array([p['ux_mm'] for p in path]);f=np.array([p['cell_force_N'] for p in path])
    applied=np.r_[0,np.cumsum(.5*(f[:-1]+f[1:])*np.diff(x))]
    native=table(folder/'history.csv');h=native[np.isin(native['set'],times+1)]
    assert np.allclose(h['ux_mm'],x,atol=1e-7,rtol=0) and np.allclose(h['fx_N'],f,atol=1e-5)
    assert abs(np.trapezoid(h['fx_N'],h['ux_mm'])-applied[-1])<1e-6
    steps=[dict(native_set=int(k+1),travel_mm=float(x[i]),external_cell_work_mJ=float(applied[i]),
        stored_case_mJ=float(gain[i,0]),stored_screws_mJ=float(gain[i,1]),
        integrated_case_force_work_mJ=float(direct[i,0]),integrated_screw_force_work_mJ=float(direct[i,1])) for i,k in enumerate(times)]
    assert abs(sum(m['support_XYZ_N'][0] for m in mounts[times[-1]])+path[-1]['screw_path_N'])<1e-5
    assert np.isclose(sum(m['beam_energy_mJ'] for m in mounts[times[-1]])-
                      sum(m['beam_energy_mJ'] for m in mounts[times[0]]),gain[-1,1])
    result=dict(terminal_mounts=mounts[times[-1]],maximum_collar_force_error_N=collar_force_error,
        maximum_collar_moment_error_Nmm=collar_moment_error,max_support_component_residual_N_or_Nmm=support_error,case=case,campaign=campaign,rst_sha256=hashes['pull.rst'],deck_sha256=hashes['model.inp'],
        displacement_check_sha256=digest(ROOT/'.runtime/post'/campaign/case/'pull_case_energy/pilot_audit.json'),
        max_bearing_translation_residual_mm=max_ring_error,largest_internal_beam_residual_fraction=internal_fraction,
        max_energy_force_work_relative_discrepancy=discrepancy.tolist(),endpoint_fractions_of_cell_work=(gain[-1]/applied[-1]).tolist(),
        history=steps,scope='Incremental recoverable energy of the linear-elastic PLA and four screws from washer lock. '
        'The external work also loads the nickel, the contacts and other fixture components.')
    write_json(ROOT/'validation/pulls'/(case+'_energy.json'),result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('case');p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args();recover(a.case,a.campaign)

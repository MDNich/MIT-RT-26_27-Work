"""Sum stored physical reactions on the eight fixed stand-offs throughout a closed installation."""
import sys

import numpy as np
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from audit_local import ROOT,read,table
from film_identity import verified,write_json
from native_rst import read_rst


def run(case,campaign):
    receipt = ROOT/'.runtime/receipts'/campaign/case
    ledger = read(receipt/'archived.json')
    status = read(receipt/'status.json')
    assert (ledger['case'],ledger['campaign']) == (case,campaign) and status['phase']=='solver_complete'
    folder = ROOT/'.runtime/archive'/campaign/case
    hashes = {f['name']:f['sha256'] for f in ledger['files']}
    verified(folder/'file.rst',hashes['file.rst'])
    proof = ROOT/'validation/global'/f'{case}.json'
    if not proof.is_file():
        proof = ROOT/'validation/review_global'/f'{case}.json'
    assert read(proof)['rst_sha256'] == hashes['file.rst']
    rst = read_rst(folder/'file.rst')
    ids = np.sort(rst.mesh.node_components['_FIXEDSU'])
    assert len(ids)==len(np.unique(ids))==781
    ix = np.searchsorted(rst.mesh.nnum,ids)
    assert np.array_equal(rst.mesh.nnum[ix],ids) and np.all(rst.mesh.node_angles[ix]==0)
    xyz = rst.mesh.nodes[ix]
    # The original fixed selection includes edge nodes below the common top plane.
    tree = cKDTree(xyz)
    regions = []
    for radius in (.003,.008):
        edges = tree.sparse_distance_matrix(tree,radius,output_type='coo_matrix')
        count,labels = connected_components(edges,directed=False)
        assert count==8
        regions.append(labels)
    assert np.array_equal(*regions)
    components = sorted([np.flatnonzero(regions[0]==i) for i in range(8)],
                        key=lambda rows:tuple(np.round(xyz[rows].mean(0)[:2]*1000)))
    centers = [xyz[rows].mean(0) for rows in components]
    moment_origin = xyz.mean(axis=0)
    history = []
    last_force = None
    actuator_error = 0.
    drives = None
    if case.endswith('_surf1_static'):
        verified(folder/'board_drives.csv',hashes['board_drives.csv'])
        drives = table(folder/'board_drives.csv')
    for k,(loadstep,increment,_) in enumerate(rst._resultheader['ls_table']):
        if increment==999999:
            continue
        magnitude,node,dof = rst.nodal_reaction_forces(k)
        mask = np.isin(node,ids)
        n,j = node[mask],dof[mask]
        assert np.all(np.isin(j,[1,2,3])) and np.array_equal(np.unique(n),ids)
        force = np.zeros((len(ids),3))
        np.add.at(force,(np.searchsorted(ids,n),j-1),magnitude[mask])
        total = force.sum(axis=0)
        torque = np.cross(xyz-moment_origin,force).sum(axis=0)
        local_force = np.array([force[rows].sum(axis=0) for rows in components])
        local_moment = np.array([np.cross(xyz[rows]-center,force[rows]).sum(axis=0)
                                 for rows,center in zip(components,centers,strict=True)])
        assert np.allclose(local_force.sum(0),total,atol=1e-7)
        assert np.allclose(local_moment.sum(0)+np.cross(centers-moment_origin,local_force).sum(0),torque,atol=1e-9)
        if drives is not None:
            driven = drives[drives['set']==k+1]
            assert np.array_equal(driven['foot'],np.arange(4))
            readback = [magnitude[(node==960111+i)&(dof==3)].sum() for i in range(4)]
            assert np.allclose(readback,driven['drive_N'],rtol=2e-5,atol=1e-4)
            actuator_error = max(actuator_error,float(np.max(abs(readback-driven['drive_N']))))
        history.append(dict(native_set=k+1,loadstep=int(loadstep),time=float(rst.time_values[k]),
                            net_force_N=total.tolist(),net_moment_Nm=torque.tolist(),
                            stand_off_force_N=local_force.tolist(),stand_off_moment_about_local_center_Nm=local_moment.tolist()))
        last_force = local_force
    assert len(history) and last_force is not None
    out = dict(case=case,campaign=campaign,rst_sha256=hashes['file.rst'],support_nodes=len(ids),support_z_extent_mm=(1000*np.array([xyz[:,2].min(),xyz[:,2].max()])).tolist(),node_counts=list(map(len,components)),
               stand_off_centers_mm=(np.array(centers)*1000).tolist(),moment_origin_mm=(moment_origin*1000).tolist(),
               largest_fixed_face_net_force_N=max(float(np.linalg.norm(x['net_force_N'])) for x in history),
               largest_fixed_face_net_moment_Nm=max(float(np.linalg.norm(x['net_moment_Nm'])) for x in history),
               final_maximum_stand_off_resultant_N=float(np.linalg.norm(last_force,axis=1).max()),history=history,
               scope='Reactions on actual fixed support nodes in the unchanged global frame. Pretension and screw-head '
                     'travel are internal adjustments; their generalized forces are recorded separately.')
    if drives is not None:
        out['maximum_actuator_POST1_difference_N']=actuator_error
    write_json(ROOT/'validation/board_reactions'/f'{case}.json',out)
    print(case,out['largest_fixed_face_net_force_N'],out['largest_fixed_face_net_moment_Nm'],out['final_maximum_stand_off_resultant_N'])


if __name__=='__main__':
    run(*sys.argv[1:])

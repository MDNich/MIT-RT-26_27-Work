"""Solve the installed board's full linear tangent independently from the original modal partitions."""
import argparse
import ctypes
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from cell_rigid_fit import body_mass, fit, pose_operator, strip_height
from dmp_board_matrix import assemble
from film_identity import digest, write_json
from snug_board_flexibility import equation_modes
from snug_board_pull import AUDIT, BRANCHES, CAMPAIGN, REGISTRY, ROOT, mass_weights, positions, read
from snug_edge_cell_travel import get_geometry, surface_transfer, verify_extrema
from case_stress import source


def symmetric_product(upper, vectors):
    return upper@vectors + upper.T@vectors - upper.diagonal()[:,None]*vectors


class TangentSolver:
    """Keep one scaled Cholesky factor for the three cell loads and eigenvector controls."""
    def __init__(self, stiffness, library):
        self.scale=1/np.sqrt(stiffness.diagonal())
        scaled=stiffness.multiply(self.scale[:,None]).multiply(self.scale).tocsc()
        scaled.sort_indices()
        self.starts=np.asarray(scaled.indptr,np.int64)
        self.rows=np.asarray(scaled.indices,np.int32)
        self.values=np.asarray(scaled.data,np.float64)
        self.library=ctypes.CDLL(str(library))
        pointer=ctypes.c_void_p
        self.library.open_factor.argtypes=[ctypes.c_int,pointer,pointer,pointer,ctypes.c_ulong,pointer]
        self.library.open_factor.restype=pointer
        self.library.solve_factor.argtypes=[pointer,ctypes.c_int,pointer]
        self.library.solve_factor.restype=None
        self.library.close_factor.argtypes=[pointer]
        self.library.close_factor.restype=None
        self.sizes=np.zeros(2,np.uint64)
        self.handle=self.library.open_factor(len(self.scale),self.starts.ctypes.data,self.rows.ctypes.data,
            self.values.ctypes.data,22_000_000_000,self.sizes.ctypes.data)
        if not self.handle:
            raise RuntimeError('Full tangent Cholesky factorization failed or exceeded the workspace allowance')

    def solve(self, load):
        values=np.asfortranarray(self.scale[:,None]*load)
        self.library.solve_factor(self.handle,values.shape[1],values.ctypes.data)
        return self.scale[:,None]*values

    def close(self):
        self.library.close_factor(self.handle)


def check_modes(branch, modal, folder, rst, dofs, free, fixed, dep, G, K, M, solver, load, u):
    """Check all expanded constraints and load projections, then reconstruct three eigenvectors by backsolve."""
    selected={0,rst.nsets//2,rst.nsets-1}
    generalized_mass=symmetric_product(M,u)
    check=[]
    for j,phi in enumerate(equation_modes(branch,modal,folder,rst,dofs,range(rst.nsets))):
        x=phi[free,None]
        lam=(2*np.pi*rst.time_values[j])**2
        g_error=float(np.max(abs((G@phi-phi)[dep])))
        assert g_error<1e-7 and np.max(abs(phi[fixed]))<1e-7
        applied=x[:,0]@load
        inferred=lam*(x[:,0]@generalized_mass)
        row=dict(mode=j+1,frequency_Hz=rst.time_values[j],constraint_error=g_error,
                 generalized_force=applied.tolist(),from_full_displacements=inferred.tolist())
        if j in selected:
            mass_vector=symmetric_product(M,x)
            stiffness_vector=symmetric_product(K,x)
            target=lam*mass_vector
            recovered=solver.solve(target)
            row['native_eigen_residual']=float(np.linalg.norm(stiffness_vector-target)/np.linalg.norm(target))
            row['inverse_mode_error']=float(np.linalg.norm(recovered-x)/np.linalg.norm(x))
            row['mass_normalization']=float((x.T@mass_vector).item())
            assert row['native_eigen_residual']<3e-6 and row['inverse_mode_error']<1e-7
            assert abs(row['mass_normalization']-1)<1e-4
        check.append(row)
    actual=np.array([r['generalized_force'] for r in check])
    projected=np.array([r['from_full_displacements'] for r in check])
    error=float(np.linalg.norm(actual-projected)/np.linalg.norm(actual))
    assert error<1e-7
    return check,error


def cell_forces(dofs, free, transfer, ids, weights):
    """Three mass-distributed unit loads, in full and independent equation order."""
    keys = 8*dofs[:,0].astype(np.int64) + dofs[:,1]
    order = np.argsort(keys)
    loads = np.zeros((len(dofs),3))
    for j,w in enumerate(weights):
        take = w != 0
        loads[order[positions(keys[order],8*ids[take])],j] = w[take]
    assert np.max(abs(loads.sum(0)-1)) < 1e-12
    return loads, (loads + transfer.T@loads)[free]


def evaluate(branch, matrices, *, load_paths=False):
    d,free,fixed,dep,G,K,M,identity=matrices
    basis,folder,rst=source(branch+'_basis',CAMPAIGN)
    installed,static_folder,initial=source(branch+'_static',CAMPAIGN)
    supports=np.sort(initial.mesh.node_components['_FIXEDSU'])
    ground=np.flatnonzero(np.isin(d[:,0],supports)&(d[:,1]<3))
    assert len(supports)==781 and len(ground)==2343 and np.isin(ground,fixed).all()
    assert len(fixed)==2349 and np.min(K.diagonal())>0
    ids,W,record=mass_weights(branch)
    assert record['basis_rst_sha256']==basis['rst_sha256'] and record['static_rst_sha256']==installed['rst_sha256']
    keys=d[:,0].astype(np.int64)*8+d[:,1]
    order=np.argsort(keys)
    def indices(nodes,components):
        return order[positions(keys[order],nodes[:,None]*8+components)]
    loads,effective=cell_forces(d,free,G,ids,W)
    assert not loads[fixed].any()
    c_source=Path(__file__).with_name('board_tangent_factor.c')
    with TemporaryDirectory() as build:
        lib=Path(build)/'factor.dylib'
        subprocess.run(['clang','-O2','-dynamiclib','-framework','Accelerate',str(c_source),'-o',str(lib)],check=True)
        solver=TangentSolver(K,lib)
        try:
            disp=solver.solve(effective)
            imbalance=np.linalg.norm(symmetric_product(K,disp)-effective,axis=0)
            assert np.max(imbalance)<1.e-7
            mode_checks,projection_error=check_modes(branch,basis,folder,rst,d,free,fixed,dep,G,K,M,
                                                      solver,effective,disp)
        finally:
            solver.close()
    u=np.zeros((len(d),3));u[free]=disp;u+=G@u
    compliance=1.e6*(loads.T@u)
    work=1.e6*disp.T@symmetric_product(K,disp)
    assert np.max(abs(compliance-compliance.T))<1e-8
    assert np.max(abs(work-compliance))<1e-7 and np.linalg.eigvalsh(compliance).min()>0

    _,_,_,geom,relative_modes,_,_,_,control=get_geometry(branch,CAMPAIGN)
    groups,washer_ids,xyz,port,_,_=control
    def motions(nodes):
        return 1000*np.moveaxis(u[indices(nodes,np.arange(3))],-1,0)
    take=W[0]!=0
    cell_ids=ids[take]
    cell_mass,_=body_mass(initial,cell_ids,W[0,take],record['geometry']['176']['volume_m3'])
    op=pose_operator(cell_mass,1000*rst.mesh.nodes[positions(rst.mesh.nnum,cell_ids)])
    centre,spin=fit(op,motions(cell_ids))
    assert np.allclose(1000*centre[:,0],compliance[0],rtol=0,atol=1e-9)
    centres=[np.array(geom['washer_faces'][i]['fixture_lower_platen_centre_mm']) for i in groups]
    flat=1000*initial.mesh.nodes[positions(initial.mesh.nnum,washer_ids)]
    hole=read(ROOT/'.runtime/local_inputs/lateral_friction_locked/config.json')['hole_radius_mm']
    washer_motion=motions(washer_ids)
    frame=surface_transfer(groups,washer_ids,xyz,flat,washer_motion,port,centres,hole,5)['whole']
    relative=centre-frame['transfer']
    pose=verify_extrema(groups,washer_ids,xyz,port,washer_motion,centre,np.eye(3),relative)
    roll=-1000*strip_height()*(spin[:,1]-frame['rot'][:,1])
    nominal=branch.removesuffix('_mesh15')
    spec=read(REGISTRY)[nominal+'_cellpush_x']
    reference_ids,reference_weights,_=mass_weights(nominal)
    assert np.array_equal(ids,reference_ids) and np.allclose(W,reference_weights,rtol=0,atol=1e-14)
    prior=AUDIT/f'{branch}_cell_flexibility.json'
    frequency=np.asarray([r['frequency_Hz'] for r in mode_checks])
    amplitude=np.asarray([r['generalized_force'] for r in mode_checks])/(2*np.pi*frequency[:,None])
    H4=1e6*amplitude.T@amplitude
    unit_coordinates=np.asarray([r['generalized_force'][0] for r in mode_checks])/(2*np.pi*frequency)**2
    prior_clamp=1000*float(unit_coordinates@relative_modes[:,0])
    if prior.is_file():
        previous=read(prior)
        assert previous['basis_sha256']==basis['rst_sha256'] and previous['force_pattern_sha256']==spec['force_cards_sha256']
        retained=previous['cutoff_Hz']['4000']
        assert np.allclose(H4,retained['cell_X_compliance_um_per_N'],rtol=1e-8,atol=1e-10)
        assert abs(prior_clamp-retained['left_relative_to_its_clamps_X_um_per_N'])<1e-9
    else:
        prior=AUDIT/f'{branch}_cell_roll_exact.json'
        if prior.is_file():
            previous=read(prior)
            assert previous['basis_sha256']==basis['rst_sha256']
            assert abs(prior_clamp-previous['small_load_per_newton']['centre_X_um'])<1e-9
    assert np.linalg.eigvalsh((compliance+compliance.T)/2-H4).min()>-1e-8
    result=dict(branch=branch,case=basis['case'],basis_rst_sha256=basis['rst_sha256'],static_rst_sha256=installed['rst_sha256'],
        matrix_assembly=identity,factor_source_sha256=digest(c_source),factor_and_workspace_bytes=solver.sizes.tolist(),
        free_equation_residual_norm_N=imbalance.tolist(),max_work_discrepancy_um_per_N=float(abs(work-compliance).max()),
        native_mode_checks=mode_checks,relative_generalized_force_check=projection_error,
        force_cards_sha256=spec['force_cards_sha256'],mass_weights_sha256=record['mass_weights_sha256'],
        retained_projection_sha256=digest(prior) if prior.is_file() else None,cell_order=['left','middle','right'],cell_X_um_per_N=compliance.tolist(),
        left_relative_to_its_clamps_X_um_per_N=(1000*relative[:,0]).tolist(),left_relative_roll_X_um_per_N=roll.tolist(),
        left_strip_height_X_um_per_N=(1000*relative[:,0]-roll).tolist(),washer_pose_check=pose,
        four_kHz_minus_full_relative_pct=100*(prior_clamp/(1000*relative[0,0])-1),
        scope='Independent static solution of the original installed modal tangent. Each column applies one newton '
              'along PCB X to the mass of one cell. Contact and material tangents retain their installed states.')
    if load_paths:
        from snug_pocket_load_path import recover
        recover(branch,basis,folder,rst,installed,static_folder,d,u,compliance)
    else:
        write_json(AUDIT/f'{branch}_full_board_tangent.json',result)
    print(branch,compliance[:,0].tolist(),1000*relative[0,0],roll[0],flush=True)


def run(branch, *, load_paths=False):
    case=branch+'_basis'
    ledger=read(ROOT/'.runtime/receipts'/CAMPAIGN/case/'archived.json')
    assert ledger['case']==case and ledger['campaign']==CAMPAIGN
    evaluate(branch,assemble(ROOT/'.runtime/archive'/CAMPAIGN/case,{r['name']:r['sha256'] for r in ledger['files']}),load_paths=load_paths)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('branch',choices=(*BRANCHES,'snug125_nylon_mesh15','snug125_aluminium_mesh15'))
    p.add_argument('--load-paths',action='store_true',help='Recover cell-to-strip and cell-to-case force increments')
    args=p.parse_args()
    run(args.branch,load_paths=args.load_paths)

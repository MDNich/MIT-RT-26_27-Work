"""Fit translations and rotations to a cell's quadratic-solid displacement using its material mass."""
import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.sparse import coo_matrix
from scipy.spatial.transform import Rotation

from audit_local import ROOT,read
from film_identity import verified
from local_equilibrium import positions

EDGES=np.array([(0,1),(1,2),(2,0),(0,3),(1,3),(2,3)])


def strip_height():
    file=ROOT/'.runtime/local_inputs/lateral_friction_locked/mesh.json'
    verified(file,read(ROOT/'validation/local_inputs.json')['lateral_friction_locked']['files']['mesh.json'])
    mesh=read(file);ids=np.unique(np.asarray(mesh['elements'])[np.array(mesh['region'])=='flat'])
    z=np.array([mesh['nodes'][str(n)][2] for n in ids])
    assert np.ptp(z)<1e-7
    return float(z.mean()-mesh['nodes'][str(mesh['pilot'])][2])


def integrate_mass(points, elem, degree):
    x=points[elem]-points[elem[:,:1]]
    g,w=leggauss(degree);g=(g+1)/2;w/=2
    grad=np.vstack((-np.ones(3),np.eye(3)))
    basis=[];weights=[]
    for i,a in enumerate(g):
        for j,b in enumerate(g):
            for k,c in enumerate(g):
                L=np.array([(1-a)*(1-b)*(1-c),a,(1-a)*b,(1-a)*(1-b)*c])
                N=np.r_[L*(2*L-1),4*L[EDGES].prod(1)]
                dN=np.vstack(((4*L[:,None]-1)*grad,
                              4*(L[EDGES[:,0],None]*grad[EDGES[:,1]]+L[EDGES[:,1],None]*grad[EDGES[:,0]])))
                J=np.linalg.det(x.transpose(0,2,1)@dN)
                assert J.min()>0 and abs(N.sum()-1)<1e-14
                weights.append(J*w[i]*w[j]*w[k]*(1-a)**2*(1-b));basis.append(N)
    shape=np.stack(basis)
    values=np.einsum('qe,qi,qj->eij',np.stack(weights),shape,shape,optimize=True)
    V=float(values.sum())
    M=coo_matrix((values.ravel(),(np.broadcast_to(elem[:,:,None],values.shape).ravel(),
                                 np.broadcast_to(elem[:,None,:],values.shape).ravel())),shape=(len(points),len(points))).tocsr()
    return M/V,V


def body_mass(raw, ids, weights, expected_volume):
    grid=raw.grid.cell_data
    numbers=np.sort(grid['ansys_elem_num'][(grid['ansys_elem_type_num']==187)&(grid['ansys_material_type']==176)])
    order=np.argsort(raw.mesh.enum);indices=order[positions(raw.mesh.enum[order],numbers)]
    nodes=np.stack([raw.mesh.elem[i][10:20] for i in indices])
    assert nodes.shape==(len(numbers),10) and np.array_equal(np.unique(nodes),ids)
    elem=positions(ids,nodes.ravel()).reshape(nodes.shape)
    ref=1000*raw.mesh.nodes[positions(raw.mesh.nnum,ids)]
    M5,V5=integrate_mass(ref,elem,5)
    M,V=integrate_mass(ref,elem,6)
    change=float(abs(M5-M).max())
    assert abs(V/V5-1)<1e-10 and abs(V/1.e9/expected_volume-1)<1e-9 and change<1e-10, (V5,V,expected_volume,change)
    assert np.max(abs(np.asarray(M.sum(1)).ravel()-weights))<1e-12
    return M,dict(volume_mm3=V,elements=len(elem),quadrature_max_entry_difference=change)


def pose_operator(M,xyz):
    w=np.asarray(M.sum(1)).ravel()
    x=xyz-w@xyz
    moment=M@x
    cov=x.T@moment
    inertia=np.trace(cov)*np.eye(3)-cov
    assert np.linalg.eigvalsh(inertia).min()>1.
    return w,x,moment,inertia


def fit(operator,u):
    w,x,moment,I=operator
    translation=np.einsum('n,snc->sc',w,u)
    spin=np.linalg.solve(I,np.cross(moment[None],u).sum(1).T).T
    return translation,spin


def check_pose(M,operator,delta):
    w,x,moment,_=operator
    v,omega=fit(operator,delta[None])
    y=x+delta-v[0]
    a,_,bt=np.linalg.svd(moment.T@y)
    R=(a*[1.,1.,np.linalg.det(a@bt)])@bt
    err=y-x@R
    radians=Rotation.from_matrix(R.T).as_rotvec()
    return dict(finite_rotvec_rad=radians.tolist(),small_rotvec_rad=omega[0].tolist(),
                fitted_residual_rms_mm=float(np.sqrt(max(0.,np.sum(err*(M@err))))),
                fitted_residual_max_nodal_mm=float(np.linalg.norm(err,axis=1).max()))

"""Independently refine the high-Y tab corner with cut-face motion from the nonlinear nylon pull."""
import argparse
from pathlib import Path

import numpy as np
from ansys.mapdl import reader
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu

from audit_local import ROOT, read
from case_stress import corners
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_mount_reactions import ring_nodes
from snug_tab_crossing import local_points, native_geometry
from snug_tab_edge import OFFSET, FORWARD
from stage_snug_fit import AUDIT, INPUTS, MESH, STEP, STEP_HASH
from tab_seating import read_point_file

CASE = FORWARD+'_m15'
EDGES = np.array([(0,1),(1,2),(2,0),(0,3),(1,3),(2,3)])
DL = np.vstack((-np.ones(3),np.eye(3)))
BARY = np.vstack((np.eye(4),np.eye(4)[EDGES].mean(1)))
CHILDREN = np.array([[0,4,6,7],[4,1,5,8],[6,5,2,9],[7,8,9,3],
                     [4,9,6,7],[4,9,7,8],[4,9,8,5],[4,9,5,6]])


def shape(lam):
    return np.concatenate((lam*(2*lam-1),4*lam[...,EDGES[:,0]]*lam[...,EDGES[:,1]]),axis=-1)


def gradient(lam):
    return np.vstack(((4*lam[:,None]-1)*DL,
                      4*(lam[EDGES[:,0],None]*DL[EDGES[:,1]]+lam[EDGES[:,1],None]*DL[EDGES[:,0]])))


def reference(level, alternate):
    children = BARY[CHILDREN].copy()
    if alternate:
        children = children[:, :, [0,2,3,1]]
    # Use positive orientations for all eight sub-tetrahedra.
    for child in children:
        if np.linalg.det(child[1:,1:]-child[:1,1:]) < 0:
            child[[1,2]] = child[[2,1]]
    corners = np.eye(4)[None]
    for _ in range(level):
        corners = (children[None] @ corners[:,None]).reshape(-1,4,4)
    lam = BARY @ corners
    assert np.allclose(lam.sum(-1),1)
    assert np.allclose(np.linalg.det(corners[:,1:,1:]-corners[:,:1,1:]),8.**-level)
    return lam


def build_patch(source, threshold):
    x = source['xyz']; t = source['connectivity']
    mask = source['distance'] < threshold
    parent = np.flatnonzero(mask)
    vertices = t[parent,:4]
    original = x[t[parent]]
    assert np.all(mask[(t[:,:4]==source['root_node']).any(1)])
    faces = np.stack([vertices[:,[j for j in range(4) if j!=i]] for i in range(4)],axis=1)
    ordered = np.sort(faces,axis=2).reshape(-1,3)
    _, index, counts = np.unique(ordered,axis=0,return_inverse=True,return_counts=True)
    cut = np.zeros(len(ordered),bool)
    for k in np.flatnonzero(counts[index].ravel()==1):
        cut[k] = tuple(ordered[k]) not in source['skin']
    cut = cut.reshape(-1,4)
    assert cut.any() and not np.intersect1d(t[parent],source['tied']).size
    assert set(np.unique(t[parent])).isdisjoint(source['loaded_contact_nodes'])
    native_ids = positions(source['native_ids'],t[parent].ravel()+OFFSET).reshape(-1,10)
    native = source['u'][:,native_ids].transpose(1,2,3,0)
    return parent, original, native, cut, int((counts==1).sum())


def interpolate(original, native, cut, level, alternate):
    lam=reference(level, alternate)
    shapes=shape(lam)
    points=np.einsum('sni,eid->esnd',shapes,original)
    _, first, inverse=np.unique(np.round(points.reshape(-1,3),9),axis=0,return_index=True,return_inverse=True)
    coords=points.reshape(-1,3)[first]
    elems=inverse.reshape(-1,10)
    assert np.max(abs(coords[elems].reshape(points.shape)-points)) < 2.e-9
    boundary=np.einsum('sni,ei->esn',(lam==0).astype(int),cut.astype(int))>0
    fixed=np.unique(elems[boundary.reshape(-1,10)])
    # Evaluate native displacements at the new nodes from the original quadratic field.
    orig_element, site = np.divmod(first, shapes.shape[0]*10)
    coefficients=shapes.reshape(-1,10)[site]
    prescribed=np.einsum('ni,nijd->njd',coefficients,native[orig_element])
    return coords,elems,fixed,prescribed


def operators(local, gp):
    d=gradient(gp)
    jac=local.transpose(0,2,1)@d
    det=np.linalg.det(jac)
    assert det.min()>0
    grad=d@np.linalg.inv(jac)
    B=np.zeros((len(local),6,30))
    for a in range(3):
        B[:,a,a::3]=grad[:,:,a]
    for a,(i,j) in enumerate(((0,1),(1,2),(0,2)),3):
        B[:,a,i::3]=grad[:,:,j]
        B[:,a,j::3]=grad[:,:,i]
    return B,det


def material(deck):
    import re
    def prop(name):
        return float(re.search(r'(?im)^MP,'+name+r',850,([^,\s]+)',deck)[1])
    ex=np.array([prop('EX'),prop('EY'),prop('EZ')])
    compliance=np.diag(1/np.r_[ex,[prop(k) for k in ('GXY','GYZ','GXZ')]])
    for i,j,k in ((0,1,'PRXY'),(1,2,'PRYZ'),(0,2,'PRXZ')):
        compliance[i,j]=compliance[j,i]=-prop(k)/ex[i]
    stiffness=np.linalg.inv(compliance)
    assert np.linalg.eigvalsh(stiffness).min()>0
    return stiffness


def quadrature(higher):
    if higher:
        from numpy.polynomial.legendre import leggauss
        grid,weights=leggauss(3);grid=(grid+1)/2;weights/=2
        for i,a in enumerate(grid):
            for j,b in enumerate(grid):
                for k,c in enumerate(grid):
                    yield np.array([(1-a)*(1-b)*(1-c),a,(1-a)*b,(1-a)*(1-b)*c]),weights[i]*weights[j]*weights[k]*(1-a)**2*(1-b)
    else:
        base=(5-np.sqrt(5))/20
        for gp in np.full((4,4),base)+np.eye(4)*(1-4*base):
            yield gp,1/24


def matrix(coords, elems, D, higher):
    nd=3*len(coords);K=None
    rule=list(quadrature(higher))
    for start in range(0,len(elems),512):
        t=elems[start:start+512]
        xyz=coords[t]-coords[t[:,:1]]
        Ke=np.zeros((len(t),30,30))
        for gp,weight in rule:
            B,det=operators(xyz,gp)
            Ke+=(B.transpose(0,2,1)@(D@B))*(det*weight)[:,None,None]
        dof=(3*t[:,:,None]+np.arange(3)).reshape(-1,30)
        rows=np.broadcast_to(dof[:,:,None],Ke.shape).ravel()
        cols=np.broadcast_to(dof[:,None,:],Ke.shape).ravel()
        part=coo_matrix((Ke.ravel(),(rows,cols)),shape=(nd,nd)).tocsr()
        K=part if K is None else K+part
    return K


def remove_rotation(coords, fixed, displacement):
    centre=coords[fixed].mean(0);x=coords-centre
    corrected=displacement.copy()
    for i in range(displacement.shape[2]):
        moved=x+displacement[:,:,i];moved-=moved[fixed].mean(0)
        a,_,b=np.linalg.svd(x[fixed].T@moved[fixed])
        R=(a*[1.,1.,np.linalg.det(a@b)])@b
        corrected[:,:,i]=moved@R.T-x
    return corrected


def exterior_nodes(tets, expected_faces):
    indices=[]
    for a,b,c in ((0,1,2),(0,1,3),(0,2,3),(1,2,3)):
        mids=[4+int(np.flatnonzero((np.sort(EDGES,axis=1)==sorted(edge)).all(1))[0]) for edge in ((a,b),(a,c),(b,c))]
        indices.append([a,b,c,*mids])
    faces=tets[:,indices].reshape(-1,6)
    keys=np.sort(faces[:,:3],axis=1)
    _,first,inverse,counts=np.unique(keys,axis=0,return_index=True,return_inverse=True,return_counts=True)
    assert counts.max()==2 and (counts==1).sum()==expected_faces
    assert np.array_equal(np.sort(faces,axis=1),np.sort(faces[first],axis=1)[inverse.ravel()])
    return np.unique(faces[first[counts==1]])


def volume_stress(x,t,states,D):
    # Integrate on descendants of precisely the original incident tetrahedra.
    # Native corner-stress averages are checked against higher-order quadrature below.
    local=x[t]-x[t[:,:1]]
    dofs=states[t].reshape(len(t),30,-1)
    base=(5-np.sqrt(5))/20
    gps=np.full((4,4),base)+np.eye(4)*(1-4*base)
    volume=0.;integral=np.zeros(dofs.shape[-1])
    for gp in gps:
        B,det=operators(local,gp);weights=det/24
        value=(D[2]@B)[:,None,:]@dofs
        integral+=weights@value[:,0];volume+=weights.sum()
    return float(volume),(integral/volume).tolist()


def native_average(x, s):
    from numpy.polynomial.legendre import leggauss
    results=[]
    for degree in (3,5):
        g,w=leggauss(degree);g=(g+1)/2;w/=2
        volume=0.;integral=0.
        for i,a in enumerate(g):
            for j,b in enumerate(g):
                for k,c in enumerate(g):
                    l=np.array([(1-a)*(1-b)*(1-c),a,(1-a)*b,(1-a)*(1-b)*c])
                    jac=x.transpose(0,2,1)@gradient(l)
                    weight=np.linalg.det(jac)*(1-a)**2*(1-b)*w[i]*w[j]*w[k]
                    volume+=weight.sum();integral+=weight@(s@l)
        results.append((volume,integral/volume))
    assert np.allclose(*results,rtol=1e-7,atol=1e-9)
    return results[-1]


def compute(source, radius, level, alternate=False, higher=False):
    parents,original,native,cut,base_exterior=build_patch(source,radius)
    x,t,fixed,disp=interpolate(original,native,cut,level,alternate)
    u=remove_rotation(x,fixed,disp)
    ref=u.copy()
    K=matrix(x,t,source['D'],higher)
    fixed_dof=(3*fixed[:,None]+np.arange(3)).ravel()
    free=np.setdiff1d(np.arange(3*len(x)),fixed_dof)
    vals=u.reshape(3*len(x),-1)
    # A uniform strain and a rigid translation are exact under quadratic interpolation.
    surface=exterior_nodes(t,base_exterior*(4**level))
    centre=x.mean(0)
    patch_values=(x-centre)@np.array([[.001,.002,.003],[.001,-.002,.0004],[-.003,.002,.004]])
    B,_=operators(x[t[:1]]-x[t[:1,:1]],np.full(4,.25))
    eps=B[0]@patch_values[t[0]].ravel()
    assert np.allclose(eps,[.001,-.002,.004,.003,.0024,0.],atol=1e-11)
    interior=np.setdiff1d(np.arange(len(x)),surface)
    assert len(interior)>0 and np.max(abs((K@patch_values.ravel()).reshape(-1,3)[interior]))<1e-6
    assert set(fixed).issubset(surface)
    assert abs(K@np.tile([.13,-.7,.41],len(x))).max()<1e-7
    A=K[free][:,free].tocsc();rhs=-(K[free][:,fixed_dof]@vals[fixed_dof])
    vals[free]=splu(A).solve(rhs)
    residual=K@vals
    assert abs(residual[free]).max()<1.e-6
    root_position=source['xyz'][source['root_node']]
    root,=np.flatnonzero(np.linalg.norm(x-root_position,axis=1)<1e-7)
    assert root not in fixed
    te,local_corner=np.where(t[:,:4]==root)
    stress=np.empty((len(te),vals.shape[1]))
    for i,(el,corner) in enumerate(zip(te,local_corner,strict=True)):
        elx=x[t[el]];B,_=operators((elx-elx[0])[None],np.eye(4)[corner])
        stress[i]=source['D'][2]@B[0]@u[t[el]].reshape(30,-1)
    parent_star=(source['connectivity'][parents,:4]==source['root_node']).any(1)
    measure=volume_stress(x,t[np.repeat(parent_star,8**level)],u,source['D'])
    assert abs(measure[0]-source['native_corner'][-1]['volume_mm3'])<2e-6
    assert np.shares_memory(u,vals) and np.array_equal(vals[fixed_dof],ref.reshape(3*len(x),-1)[fixed_dof])
    err=np.linalg.norm(u-ref,axis=1).max(0)
    parent_ids=1200001+parents[te//(8**level)]
    native_peak=np.array([a['max_MPa'] for a in source['native_corner']])
    peak=stress.max(axis=0)
    seen=np.flatnonzero(peak>=40.5)
    result=dict(alternate_diagonal=alternate,stiffness_quadrature_points=len(list(quadrature(higher))),
                star_volume_mm3=measure[0],star_mean_layer_tension_MPa=measure[1],radius_mm=radius,subdivisions=2**level,parent_elements=len(parents),elements=len(t),
                nodes=len(x),cut_nodes=len(fixed),max_free_dof_residual_N=float(abs(residual[free]).max()),
                root_incident_elements=len(te),max_node_error_relative_to_native_um=(1000*err).tolist(),
                high_Y_root_max_layer_tension_MPa=peak.tolist(),high_Y_root_min_layer_tension_MPa=stress.min(0).tolist(),
                peak_corner_parent_element=(parent_ids[stress.argmax(0)]).tolist(),
                difference_from_native_peak_at_last_station_MPa=float(peak[-1]-native_peak[-1]),
                first_sample_above_coupon_native_set=int(source['sets'][seen[0]]) if len(seen) else None)
    return result


def setup(folder):
    record=AUDIT/f'{CASE}_{folder.name}_checkpoint.json';proof=read(record)
    assert folder.name=='ls3_ss24' and proof['first_excluded_set']==33 and proof['case']==CASE
    path=folder/'pull.rst';verified(path,proof['rst_sha256']);raw=reader.read_binary(path)
    corner_path=AUDIT/f'{CASE}_{folder.name}_tab_corners.json'
    corner_proof=read(corner_path)
    assert corner_proof['checkpoint_sha256']==digest(record)
    peak=corner_proof['stations'][-1]['metrics']['layer_tension_MPa']
    spec=read(AUDIT/'local_inputs_m15.json')[CASE]
    assert spec['input_sha256']==proof['input_sha256'] and spec['mesh_sha256']==corner_proof['mesh_sha256']
    assert corner_proof['STEP_sha256']==STEP_HASH
    verified(STEP,STEP_HASH)
    meshfile=MESH/'case_1.5.npz';verified(meshfile,spec['mesh_sha256'])
    deck=INPUTS/CASE/'model.inp';verified(deck,spec['input_sha256'])
    rules=deck.read_text();rings,_=ring_nodes(rules)
    with np.load(meshfile) as m:
        native_geometry(raw,m,rules)
        x=local_points(m['points']);t=m['tets'][:,[0,1,2,3,4,5,6,7,9,8]]
        skin={tuple(row) for row in np.sort(np.vstack([m[k][:,:3] for k in m.files if k.isdigit()]),axis=1)}
    root=peak['node']-OFFSET
    dist=np.linalg.norm(x[t[:,:4]].mean(1)-x[root],axis=1)
    ids=np.unique(t[dist<3.75])+OFFSET;sets=list(range(1,proof['first_excluded_set']+1))
    out=folder/'dpf_tab_submodel_all'
    u,_=read_point_file(path,out,proof['rst_sha256'],sets,ids.tolist())
    grid=raw.grid.cell_data
    contact_ids=grid['ansys_elem_num'][(grid['ansys_etype']==862)&np.isin(grid['ansys_real_constant'],[861,862])]
    ordered=np.argsort(raw.mesh.enum)
    elems=raw.mesh.elem
    loaded=set();root_values=[]
    root_elements=np.flatnonzero((t[:,:4]==root).any(1))+1200001
    for station in sets:
        enum,data,_=raw.element_solution_data(station-1,'EMN')
        indices=positions(enum,contact_ids)
        active=[int(cid) for cid,i in zip(contact_ids,indices,strict=True)
                if data[i] is not None and len(data[i]) and max(data[i][:4])>=2]
        for j in ordered[positions(raw.mesh.enum[ordered],np.array(active,dtype=int))]:
            loaded.update(int(n)-OFFSET for n in elems[j][10:18])
        n,s=corners(raw,station-1,'ENS',root_elements,6)
        zz=s[n==peak['node'],2]
        assert np.array_equal(n.reshape(-1,4),OFFSET+t[root_elements-1200001,:4])
        xx=x[t[root_elements-1200001]]
        vol,average=native_average(xx-xx[:,:1],s[:,2].reshape(-1,4))
        root_values.append(dict(volume_mm3=vol,star_mean_MPa=average,native_set=station,travel_mm=proof['states'][station-1]['travel_mm'],
                               max_MPa=float(zz.max()),min_MPa=float(zz.min())))
    assert abs(root_values[-1]['max_MPa']-peak['peak'])<1e-7
    return dict(xyz=x,connectivity=t,root_node=root,distance=dist,skin=skin,D=material(rules),native_ids=ids,
                u=u,tied=np.concatenate(list(rings.values()))-OFFSET,loaded_contact_nodes=loaded,sets=sets,
                native_corner=root_values,checkpoint_sha256=digest(record),DPF_source_sha256=proof['rst_sha256'],
                DPF_displacements_sha256=digest(out/'displacements.bin'),mesh_sha256=spec['mesh_sha256'],
                input_sha256=spec['input_sha256'],step_sha256=STEP_HASH)


def run(folder):
    source=setup(folder)
    results=[]
    requested=[(radius,level,False,False) for radius,levels in ((1.8,range(4)),(2.75,range(4)),(3.75,range(3)))
               for level in levels]
    requested.extend((1.8,level,True,False) for level in (1,2,3))
    requested.extend((1.8,level,False,True) for level in (0,2))
    for radius,level,alternate,higher in requested:
        result=compute(source,radius,level,alternate,higher)
        results.append(result)
        print(radius,level,alternate,higher,result['high_Y_root_max_layer_tension_MPa'][-1],flush=True)
    native=source['native_corner']
    for row in results:
        if row['subdivisions']==1:
            assert np.max(abs(np.asarray(row['high_Y_root_max_layer_tension_MPa'])-[v['max_MPa'] for v in native])) < .30
            assert max(row['max_node_error_relative_to_native_um']) < .1
    data={k:source[k] for k in ('checkpoint_sha256','DPF_source_sha256','DPF_displacements_sha256','mesh_sha256','input_sha256','step_sha256')}
    data.update(case=CASE,checkpoint=folder.name,material_stiffness_MPa=source['D'].tolist(),native=native,
                independent=results,units='mm, N, MPa',region='High-Y, low-X tab root; same nine original incident tetrahedra for every volume average.',
                scope='Independent small-strain orthotropic elasticity with fitted rigid motion removed. Prescribed cut nodes follow the native '
                      'quadratic displacement fields at each saved equilibrium. Both contact pairs and the screw ties are outside the free region. '
                      'This local calculation cannot redistribute force to the rest of the assembly or predict fracture.')
    write_json(AUDIT/'nylon_forward_tab_submodel.json',data)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder',type=Path)
    run(p.parse_args().folder)

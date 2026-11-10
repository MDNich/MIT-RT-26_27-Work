"""Independently confirm a sampled outer-cell crossing on the two actual quadratic patches."""
import argparse
import numpy as np
from scipy.optimize import least_squares
from vtkmodules.vtkCommonDataModel import vtkTriangle

from audit_local import ROOT,read
from basis_comparison import field_files
from case_stress import source
from early_cell_clearance import bezier,outer_faces,subdivision_weights,unresolved
from film_cell_contact import TOL_MM,candidate_pairs,separate_convex_hulls
from film_cell_timestep import refined_coordinates
from film_identity import digest,verified,write_json
from motion_surface import displacement_basis
from seeded_motion import FS,participation
from snug_shell_drive_sampling import native_startup
from stage_snug_fit import AUDIT


def basis(p):
    u,v,w=p
    return np.array([u*u,v*v,w*w,2*u*v,2*v*w,2*w*u])


def normal(face,p):
    u,v,w=p
    first=np.array([2*u,0,-2*w,2*v,-2*v,2*(w-u)])@face
    second=np.array([0,2*v,-2*w,2*u,2*(w-v),-2*u])@face
    n=np.cross(first,second)
    return n/np.linalg.norm(n)


def confirm(a0,b0):
    ia,ib=candidate_pairs((a0.min(1)-TOL_MM,a0.max(1)+TOL_MM),(b0.min(1)-TOL_MM,b0.max(1)+TOL_MM))
    a,b=a0[ia],b0[ib]
    child=subdivision_weights()
    corners=np.eye(3)
    mids=(corners+np.roll(corners,-1,axis=0))/2
    sub=np.vstack((corners,mids))[[[0,3,5],[3,1,4],[5,4,2],[3,4,5]]]
    pa=np.tile(corners,(len(a),1,1));pb=pa.copy()
    for level in range(9):
        keep=unresolved(a,b,TOL_MM)
        a,b,ia,ib,pa,pb=[x[keep] for x in (a,b,ia,ib,pa,pb)]
        if len(a):
            use=separate_convex_hulls(a,b)
            a,b,ia,ib,pa,pb=[x[use] for x in (a,b,ia,ib,pa,pb)]
        if not len(a):break
        if level>=3:
            for m,(x,y) in enumerate(zip(a,b,strict=True)):
                if not vtkTriangle.TrianglesIntersect(*x[:3],*y[:3]):continue
                # Both maps span the closed triangle. An interior zero with nonparallel normals
                # lies on a curve crossing both physical surfaces.
                # Extend the local starting point over its entire parent face. A coarse
                # planar crossing may lie just across a subtriangle edge on the curved map.
                parent_a=a0[ia[m]];parent_b=b0[ib[m]];origin=parent_a[0]
                scale=max(np.ptp(parent_a,axis=0).max(),np.ptp(parent_b,axis=0).max())
                sx,sy=(parent_a-origin)/scale,(parent_b-origin)/scale
                def bary(uv):return np.r_[uv,1-uv.sum()]
                def gap(z):return basis(bary(z[:2]))@sx-basis(bary(z[2:]))@sy
                start=np.r_[pa[m].mean(0)[:2],pb[m].mean(0)[:2]]
                fit=least_squares(gap,start,method='dogbox',gtol=1.e-14,
                                  ftol=1.e-14,xtol=1.e-14,max_nfev=100)
                uv0,uv1=bary(fit.x[:2]),bary(fit.x[2:])
                xx=basis(uv0)@a0[ia[m]];yy=basis(uv1)@b0[ib[m]]
                dist=np.linalg.norm(xx-yy)
                sine=np.linalg.norm(np.cross(normal(a0[ia[m]],uv0),normal(b0[ib[m]],uv1)))
                if dist<1.e-9 and min(uv0.min(),uv1.min())>1.e-7 and sine>1.e-5:
                    return dict(PLA_face=int(ia[m]),cell_face=int(ib[m]),PLA_barycentric=uv0.tolist(),
                                cell_barycentric=uv1.tolist(),quadratic_point_xyz_mm=xx.tolist(),
                                residual_mm=float(dist),normal_cross_magnitude=float(sine),search_subdivision=level)
        if level<8:
            if level>=3 and len(a)>20000:break
            a=np.repeat(child@a[:,None],4,axis=1).reshape(-1,6,3)
            b=np.tile(child@b[:,None],(1,4,1,1)).reshape(-1,6,3)
            pa=np.repeat(sub@pa[:,None],4,axis=1).reshape(-1,3,3)
            pb=np.tile(sub@pb[:,None],(1,4,1,1)).reshape(-1,3,3)
            ia=np.repeat(ia,16);ib=np.repeat(ib,16)
    return None


def run(variant,method,campaign):
    path=AUDIT/(variant+'_outer_onset_Z_'+method+'.json')
    onset=read(path)
    proof,folder,rst=source(variant+'_basis',campaign)
    assert onset['basis_rst_sha256']==proof['rst_sha256'] and onset['method']==method
    offsets=(0,1,2,4,8,16,32)
    samples=np.unique([0]+[r['first_intersecting_sample']+delta for r in onset['cells'].values()
                           if r['first_intersecting_sample'] is not None for delta in offsets
                           if r['first_intersecting_sample']+delta<onset['samples']])
    motion=read(ROOT/'validation/independent_motion'/(variant+'_motion_Z.json'))
    if method=='native':
        q,source_record=native_startup(motion,campaign,rst.time_values,samples)
        assert source_record==onset['checks']
    else:
        load=ROOT/'.runtime/motion_loads/Z.txt';log=folder/'solve.out'
        verified(load,motion['input_sha256']);verified(log,motion['modal_listing_sha256'])
        acc=np.loadtxt(load,skiprows=1,max_rows=int(samples[-1])+1)
        q,_=refined_coordinates('linear_input_exact',acc[:,1],samples,rst.time_values,participation(log.read_text(),'Z'))
    faces=[outer_faces(rst,[m]) for m in (850,176,187)]
    ids=np.unique(np.concatenate([f.ravel() for f in faces]))
    ix=np.searchsorted(rst.mesh.nnum,ids);assert np.array_equal(rst.mesh.nnum[ix],ids)
    xyz=rst.mesh.nodes[ix]*1000
    modes=1000*displacement_basis(rst,ids,field_files(variant+'_basis',campaign,proof['rst_sha256'],rst.nsets))
    certs={}
    for i,name in enumerate(('left','right'),1):
        row=onset['cells'][name];sample=row['first_intersecting_sample']
        if sample is None:continue
        assert not row['unresolved_samples'] and row['last_contiguous_clear_sample']==sample-1
        for delta in offsets:
            station=sample+delta
            if station>=onset['samples']:break
            pos=xyz+(q[np.searchsorted(samples,station)]@modes.reshape(len(modes),-1)).reshape(-1,3)
            sets=[pos[np.searchsorted(ids,faces[j])] for j in (0,i)]
            rec=confirm(*[bezier(arr) for arr in sets])
            if rec is not None:break
        if rec is None:raise ValueError(f'No transverse intersection confirmed for {name}')
        coords=[]
        for label,arr,f in zip(('PLA','cell'),sets,(faces[0],faces[i]),strict=True):
            k=rec[label+'_face'];p=np.array(rec[label+'_barycentric'])
            shape=np.r_[p*(2*p-1),4*p[0]*p[1],4*p[1]*p[2],4*p[2]*p[0]]
            coords.append(shape@arr[k]);rec[label+'_nodes']=f[k].tolist()
        assert np.linalg.norm(coords[0]-coords[1])<1.e-9
        assert np.linalg.norm(coords[0]-rec['quadratic_point_xyz_mm'])<1.e-9
        certs[name]=dict(first_intersection_interval_ms=[1000*(sample-1)/FS,1000*station/FS],sample=station,time_s=station/FS,**rec)
        print(variant,method,name,sample,station,rec['residual_mm'],rec['normal_cross_magnitude'],flush=True)
    write_json(path.with_name(path.stem+'_witness.json'),dict(variant=variant,method=method,source_sha256=digest(path),
               cells=certs,scope='Both original six-node interpolation surfaces share the reported interior point; '
                                'their normals are nonparallel. The witness tests the fixed-tangent geometry.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('variant');p.add_argument('--method',choices=('native','exact'),required=True)
    p.add_argument('--campaign',default='nov08_01');a=p.parse_args();run(a.variant,a.method,a.campaign)

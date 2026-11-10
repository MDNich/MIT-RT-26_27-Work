"""Measure the left cell's lateral vibration relative to the two washer faces that clamp its strips."""
import argparse
import hashlib
import re

import numpy as np
from numpy.polynomial.legendre import leggauss
from vtkmodules.vtkCommonDataModel import vtkQuadraticQuad, vtkQuadraticTriangle

from audit_local import ROOT, read
from basis_comparison import field_files
from case_stress import source
from film_identity import digest, verified, write_json
from motion_surface import displacement_basis
from seeded_motion import FS
from snug_pla_vibration import full_coordinates
from stage_snug_fit import AUDIT


def face_rule(width, degree):
    """Quadrature in each native quadratic face, including the triangle reference-area factor."""
    rule = vtkQuadraticTriangle() if width == 6 else vtkQuadraticQuad()
    assert rule.GetNumberOfPoints() == width
    g, w = leggauss(degree)
    g, w = (g+1)/2, w/2
    for i, u in enumerate(g):
        for j, v in enumerate(g):
            fraction = 1-u if width == 6 else 1.
            point = [u, v*fraction, 0.]
            shape = np.empty(width)
            grad = np.empty(2*width)
            rule.InterpolateFunctions(point,shape)
            rule.InterpolateDerivs(point,grad)
            assert abs(shape.sum()-1.) < 1e-12 and np.max(abs(grad.reshape(2,-1).sum(1))) < 1e-12
            yield shape,grad.reshape(2,width),w[i]*w[j]*fraction


def washer_faces(original, centres):
    g=original.quadgrid
    groups={}
    info={}
    for mat,centre in zip((182,178),centres,strict=True):
        select=(g.cell_data['ansys_material_type']==mat)&np.isin(g.cell_data['ansys_elem_type_num'],[186,187])
        volume=g.extract_cells(select)
        ids=volume.point_data['ansys_node_num']
        xyz=1000*volume.points
        zmax=xyz[:,2].max()
        assert abs(zmax-centre[2])<.03
        entries={}
        for i in range(volume.n_cells):
            cell=volume.GetCell(i)
            for j in range(cell.GetNumberOfFaces()):
                face=cell.GetFace(j)
                points=np.array([face.GetPointId(k) for k in range(face.GetNumberOfPoints())])
                if np.max(abs(xyz[points,2]-zmax))<2e-5:
                    assert len(points) in (6,8)
                    entries.setdefault(len(points),[]).append(ids[points])
        groups[mat]={k:np.stack(v) for k,v in entries.items()}
        nn=np.unique(np.concatenate([v.ravel() for v in groups[mat].values()]))
        xy=1000*original.mesh.nodes[np.searchsorted(original.mesh.nnum,nn),:2]
        r=np.linalg.norm(xy-centre[:2],axis=1)
        assert 2.13<r.min()<2.16 and 5.38<r.max()<5.42
        info[mat]=dict(upper_plane_Z_mm=float(zmax),nodes=len(nn),faces={k:len(v) for k,v in groups[mat].items()},
                       radial_limits_mm=[float(r.min()),float(r.max())],fixture_lower_platen_centre_mm=centre.tolist())
    return groups,info


def surface_transfer(groups, ids, xyz, ref_xyz, modes, cell_centre, centres, hole_radius, degree):
    """Area integrals for least-squares translation and rotation of the two installed washer faces."""
    fixed={};port=cell_centre
    for trim in (False,True):
        area=0.
        first=np.zeros(3);second=np.zeros((3,3))
        scalar=np.zeros(len(ids));moment=np.zeros((len(ids),3))
        for (mat,by_width),centre in zip(groups.items(),centres,strict=True):
            for width,faces in by_width.items():
                n=np.searchsorted(ids,faces);assert np.array_equal(ids[n],faces)
                pos=xyz[n]-port
                for N,dN,weight in face_rule(width,degree):
                    a,b=np.einsum('cw,fwd->cfd',dN,pos)
                    da=weight*np.linalg.norm(np.cross(a,b),axis=1)
                    if trim:
                        flat=np.einsum('w,fwd->fd',N,ref_xyz[n,:2])
                        da=np.where(np.linalg.norm(flat-centre[:2],axis=1)>=hole_radius,da,0.)
                    x=np.einsum('w,fwd->fd',N,pos)
                    area+=da.sum();first+=da@x;second+=x.T@(da[:,None]*x)
                    mass=da[:,None]*N
                    np.add.at(scalar,n,mass)
                    np.add.at(moment,n,mass[:,:,None]*x[:,None,:])
        origin=first/area
        cov=second/area-np.outer(origin,origin)
        inertia=np.trace(cov)*np.eye(3)-cov
        assert np.linalg.eigvalsh(inertia).min()>1.
        scalar/=area;moment=moment/area-scalar[:,None]*origin
        assert abs(scalar.sum()-1)<1e-12 and np.linalg.norm(moment.sum(0))<1e-10
        def project(u):
            shift=np.einsum('n,mnd->md',scalar,u)
            spin=np.linalg.solve(inertia,np.cross(moment[None,:,:],u).sum(1).T).T
            return shift-np.cross(spin,origin),shift,spin
        test_v=np.array([.21,-.35,.48]);test_spin=np.array([.003,-.01,.017])
        v,_,w=project((test_v+np.cross(test_spin,xyz-port))[None])
        assert np.allclose(v[0],test_v,atol=1e-11,rtol=0) and np.allclose(w[0],test_spin,atol=1e-11,rtol=0)
        v,mean,spin=project(modes)
        fixed['outside_bore' if trim else 'whole']=dict(transfer=v,mean=mean,rot=spin,area_mm2=area,
                                                        centre_mm=port+origin)
    return fixed


def verify_extrema(groups,ids,xyz,centre,modal_washer,modal_cell,q,expected,*,return_rotations=False):
    """Fit a rigid pose directly to each reconstructed two-washer displacement field."""
    position=[];area=[];moved=[]
    fields=(q@modal_washer.reshape(len(modal_washer),-1)).reshape(len(q),len(ids),3)
    for by_width in groups.values():
        for width,faces in by_width.items():
            n=np.searchsorted(ids,faces)
            points=xyz[n]-centre
            samples=fields[:,n,:]
            for N,dN,weight in face_rule(width,4):
                a,b=np.einsum('cw,fwd->cfd',dN,points)
                area.append(weight*np.linalg.norm(np.cross(a,b),axis=1))
                position.append(np.einsum('w,fwd->fd',N,points))
                moved.append(np.einsum('w,kfwd->fdk',N,samples))
    x=np.concatenate(position);w=np.concatenate(area);u=np.concatenate(moved)
    system=np.zeros((len(x),3,6))
    system[:,:,:3]=np.eye(3)
    for j in range(3):
        system[:,:,3+j]=np.cross(np.eye(3)[j],x)
    factor=np.sqrt(w/w.sum())[:,None,None]
    fits=np.linalg.lstsq((factor*system).reshape(-1,6),(factor*u).reshape(-1,len(q)),rcond=None)[0]
    cell=q@modal_cell
    reconstructed=cell-fits[:3].T
    err=float(abs(reconstructed-expected).max())
    assert err<1e-7
    w=w/w.sum();mean=w@x;finite=[];rotations=[]
    for k in range(len(q)):
        y=x+u[:,:,k]
        end=w@y
        left,_,right=np.linalg.svd((x-mean).T@(w[:,None]*(y-end)))
        rotation=(left*np.array([1.,1.,np.linalg.det(left@right)]))@right
        finite.append(cell[k]-(end-mean@rotation))
        if return_rotations:
            rotations.append(rotation.T.tolist())
    result=dict(direct_field_fit_max_component_error_mm=err,
                finite_rotation_minus_linear_X_mm_at_extrema=(np.array(finite)[:,0]-reconstructed[:,0]).tolist())
    if return_rotations:
        result.update(finite_rotation_matrices=rotations,small_rotvec_rad=fits[3:].T.tolist())
    return result


def get_geometry(variant,campaign):
    modal,folder,rst=source(variant+'_basis',campaign)
    static,_,original=source(variant+'_static',campaign)
    evidence=read(ROOT/'validation/cell_force'/(variant+'.json'))
    assert static['rst_sha256']==evidence['static_rst_sha256'] and modal['rst_sha256']==evidence['basis_rst_sha256']
    local='bare_lateral_friction_locked'
    root=ROOT/'.runtime/archive'/campaign/local
    sha={f['name']:f['sha256'] for f in read(ROOT/'.runtime/receipts'/campaign/local/'archived.json')['files']}
    verified(root/'model.inp',sha['model.inp']);text=(root/'model.inp').read_text()
    cfg=ROOT/'.runtime/local_inputs/lateral_friction_locked'
    catalog=read(ROOT/'validation/local_inputs.json')['lateral_friction_locked']['files']
    for name in ('mesh.json','config.json'):verified(cfg/name,catalog[name])
    config=read(cfg/'config.json');mesh=read(cfg/'mesh.json')
    centres=[]
    for pilot in config['bottom_pilots']:
        card,=re.findall(rf'(?im)^N,{pilot},([^\r\n]+)',text)
        centres.append(np.fromstring(card,sep=','))
    local_pilot=np.array(mesh['nodes'][str(mesh['pilot'])])
    groups,face_info=washer_faces(original,centres)
    archive=ROOT/'.runtime/post'/campaign/(variant+'_basis')
    for name,key in [('cell_mass_weights.npz','mass_weights_sha256'),('cell_mass_mean.npz','mean_shapes_sha256')]:
        verified(archive/name,evidence[key])
    with np.load(archive/'cell_mass_weights.npz') as m:
        j,=np.flatnonzero(m['materials']==176)
        w=m['weights'][j];use=w!=0;weights=w[use];cell_ids=m['nodes'][use]
    assert abs(weights.sum()-1)<1e-10
    with np.load(archive/'cell_mass_mean.npz') as m:
        assert np.array_equal(m['frequencies_Hz'],rst.time_values)
        j,=np.flatnonzero(m['materials']==176)
        cell_modes=1000*m['mean'][j].T
    washer_ids=np.unique(np.concatenate([v.ravel() for g in groups.values() for v in g.values()]))
    ids=np.union1d(cell_ids,washer_ids)
    fields=field_files(modal['case'],campaign,modal['rst_sha256'],rst.nsets)
    u=1000*displacement_basis(rst,ids,fields)
    ci=np.searchsorted(ids,cell_ids);wi=np.searchsorted(ids,washer_ids)
    recomputed=np.einsum('n,mnd->md',weights,u[:,ci])
    assert np.allclose(recomputed,cell_modes,rtol=1e-11,atol=1e-8)
    def coords(raw,ns):
        ix=np.searchsorted(raw.mesh.nnum,ns);assert np.array_equal(raw.mesh.nnum[ix],ns)
        return raw.mesh.nodes[ix]*1000
    initial_cell=weights@coords(original,cell_ids)
    assert np.linalg.norm(local_pilot-initial_cell)<.002
    port=weights@coords(rst,cell_ids)
    xyz=coords(rst,washer_ids);reference=coords(original,washer_ids)
    rules=[surface_transfer(groups,washer_ids,xyz,reference,u[:,wi],port,centres,config['hole_radius_mm'],degree)
           for degree in (3,5)]
    whole=[r['whole'] for r in rules]
    transfer=cell_modes-whole[1]['transfer']
    diff=np.linalg.norm(whole[0]['transfer']-whole[1]['transfer'])/np.linalg.norm(transfer)
    assert diff<1e-6
    h=hashlib.sha256()
    for group in groups.values():
        for width,faces in sorted(group.items()):h.update(faces.astype('<i8').tobytes())
    geom=dict(static_sha256=static['rst_sha256'],basis_sha256=modal['rst_sha256'],local_deck_sha256=sha['model.inp'],
              local_pilot_mm=local_pilot.tolist(),original_centroid_mm=initial_cell.tolist(),locked_centroid_mm=port.tolist(),
              right_left_axis='positive PCB X points from left cell to middle cell',material_cell=176,
              washer_faces=face_info,washer_face_nodes_sha256=h.hexdigest(),cell_weights_sha256=evidence['mass_weights_sha256'],
              face_area_mm2=whole[1]['area_mm2'],fitted_origin_mm=whole[1]['centre_mm'].tolist(),
              relative_transfer_norm_change_3_to_5=diff)
    check=(groups,washer_ids,xyz,port,u[:,wi],cell_modes)
    return modal,folder,rst.time_values,geom,transfer,cell_modes-rules[1]['outside_bore']['transfer'],cell_modes,cell_modes-whole[1]['mean'],check


def measure(variant,methods,campaign):
    modal,folder,freq,geom,transfer,trim,cell,translation_only,control=get_geometry(variant,campaign)
    for method in methods:
        results={}
        for a in 'XYZ':
            q,sha,input_sha=full_coordinates(variant,campaign,method,a,modal,folder,freq)
            delta=q@transfer
            left,right=int(delta[:,0].argmin()),int(delta[:,0].argmax())
            gross=q@cell[:,0];trimmed=q@trim[:,0]
            untranslated=q@translation_only[:,0]
            results[a]=dict(coordinate_source_sha256=sha,excitation_sha256=input_sha,
                            negative_X=dict(sample=left,time_s=left/FS,simultaneous_relative_xyz_mm=delta[left].tolist()),
                            positive_X=dict(sample=right,time_s=right/FS,simultaneous_relative_xyz_mm=delta[right].tolist()),
                            rms_about_zero_X_mm=float(np.sqrt(np.mean(delta[:,0]**2))),
                            whole_cell_peak_abs_X_mm=float(abs(gross).max()),
                            without_washer_rotation_peak_abs_X_mm=float(abs(untranslated).max()),
                            outside_bore_peak_abs_X_mm=float(abs(trimmed).max()),
                            maximum_change_from_excluding_inner_rim_mm=float(abs(trimmed-delta[:,0]).max()))
            indices=[left,right]
            results[a]['direct_pose_check']=verify_extrema(*control,q[indices],delta[indices])
            del q
        write_json(AUDIT/(variant+'_edge_cell_travel_'+method+'.json'),dict(variant=variant,campaign=campaign,method=method,
                  geometry=geom,axes=results,scope='Linear changes from bolt lock. The area-weighted rigid motion of the two '
                  'left clamp washer upper faces is transported to the cell mass centroid. The reported travel is the remaining '
                  'translation along the native lateral fixture axis. This does not measure electrode sliding, case contact '
                  'force, or the capacity of a weld.'))
        print(variant,method,{a:[round(r[k]['simultaneous_relative_xyz_mm'][0],5) for k in ('negative_X','positive_X')]
                              for a,r in results.items()},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant',choices=('bare','snug125_nylon','snug125_aluminium','snug125_nylon_mesh15','snug125_aluminium_mesh15'))
    p.add_argument('--methods',nargs='+',choices=('native','independent','exact'),default=['native','exact'])
    p.add_argument('--campaign',default='nov08_01')
    args=p.parse_args();measure(args.variant,args.methods,args.campaign)

"""Check the signed displacement and equivalent stress fields used in the seven seeded movies."""
import argparse
import numpy as np
import pyvista as pv
from audit_local import ROOT,read
from film_identity import digest,verified,write_json
from seeded_motion import FS,FRAMES
from seeded_video import SUBJECTS,field_files


def case_fields(variant, subject, campaign, method):
    axis,scope,component=SUBJECTS[subject]
    basis=variant+'_basis'
    case=variant+'_motion_'+axis
    category='motion' if method=='native' else 'independent_motion'
    proof_path=ROOT/'validation'/category/(case+'.json')
    proof=read(proof_path)
    modal=read(ROOT/'validation/global'/(basis+'.json'))
    assert proof['case']==case and modal['case']==basis and proof['branch']==variant
    assert proof['campaign']==modal['campaign']==campaign and proof['basis_rst_sha256']==modal['rst_sha256']
    archive=ROOT/'.runtime/archive'/campaign/basis/'file.rst'
    verified(archive,modal['rst_sha256'])
    post=ROOT/'.runtime/post'/campaign
    clip=post/case
    if method=='independent':
        clip=clip/'independent'
    clip=clip/'coordinates.npz'
    verified(clip,proof['clip_sha256'])
    root=post/(variant+'_films')
    cache=root/subject/proof['clip_sha256']
    data=field_files(archive,clip,np.arange(len(FRAMES)),scope,component,cache,root/'pcb_stress',modal['rst_sha256'])
    assert data['identity']['coordinates_sha256']==proof['clip_sha256']
    return cache,data,digest(proof_path)


def check(variant,subject,campaign):
    axis,scope,component=SUBJECTS[subject]
    old,control,control_sha=case_fields(variant,subject,campaign,'independent')
    cache,native,native_sha=case_fields(variant,subject,campaign,'native')
    assert native['geometries']==control['geometries']
    # Confirm the same painted mesh, connectivity, and displacement indexing in both generations.
    geometry=[]
    for part in native['geometries']:
        before,after=[pv.read(d/part['file']) for d in (old,cache)]
        for key in ['points','faces']:
            assert np.array_equal(getattr(before,key),getattr(after,key))
        assert set(before.point_data.keys())==set(after.point_data.keys())
        for key in after.point_data:
            assert np.array_equal(after.point_data[key],before.point_data[key])
        geometry.append(dict(points=after.n_points,faces=after.n_cells,mesh_sha256=digest(cache/part['file'])))
    name='stress.npy' if component=='stress' else 'displacement.npy'
    a,b=[np.load(f/name,mmap_mode='r') for f in (old,cache)]
    assert a.shape==b.shape and len(a)==len(FRAMES)
    if component!='stress':
        column='XYZ'.index(component)
        a=a[:,:,column];b=b[:,:,column]
    assert a.ndim==b.ndim==2 and a.shape[1]>0
    n=len(a)
    peak=np.zeros(n)
    before_peak=np.zeros(n)
    l2=np.zeros(n)
    delta2=np.zeros(n)
    max_delta=0.
    for j in range(0,n,8):
        k=slice(j,j+8)
        previous=np.asarray(a[k],dtype=np.float64)
        current=np.asarray(b[k],dtype=np.float64)
        delta=current-previous
        peak[k]=np.max(abs(current),axis=1)
        before_peak[k]=np.max(abs(previous),axis=1)
        delta2[k]=np.einsum('ij,ij->i',delta,delta)
        l2[k]=np.einsum('ij,ij->i',current,current)
        max_delta=max(max_delta,float(abs(delta).max()))
    units='MPa' if component=='stress' else 'mm'
    scale=1. if units=='MPa' else 1000.
    visible=float(peak.max()*scale)
    full=native['peak']
    if component=='stress':
        # The original colour scale includes interior as well as visible board corners.
        assert visible <= full*(1.+1.e-6)
    else:
        assert np.isclose(visible,full,rtol=1.e-6,atol=1.e-10)
        assert np.isclose(before_peak.max()*scale,control['peak'],rtol=1.e-6,atol=1.e-10)
    relative=float(np.sqrt(delta2.sum()/l2.sum()))
    assert relative<.005 and max_delta*scale < .005*full
    i=int(peak.argmax())
    return dict(axis=axis,component=component,scope=scope,units=units,frames=n,scalar_values_per_frame=a.shape[1],
        modal_rst_sha256=native['identity']['rst_sha256'],native_audit_sha256=native_sha,independent_audit_sha256=control_sha,
        native_clip_sha256=native['identity']['coordinates_sha256'],independent_clip_sha256=control['identity']['coordinates_sha256'],
        native_scalar_file_sha256=digest(cache/name),independent_scalar_file_sha256=digest(old/name),geometry=geometry,
        native_scale_peak=full,independent_scale_peak=control['peak'],native_visible_peak=visible,peak_movie_frame=i+1,
        time_of_visible_peak_s=float(FRAMES[i]/FS),maximum_abs_value_difference=max_delta*scale,
        field_relative_L2=relative,max_frame_peak_abs_difference=float(np.max(abs(peak-before_peak))*scale))


def run(variant,campaign):
    results={}
    for subject in SUBJECTS:
        results[subject]=check(variant,subject,campaign)
        print(variant,subject,results[subject]['native_scale_peak'],results[subject]['field_relative_L2'],flush=True)
    write_json(ROOT/'validation/seeded_film_fields'/(variant+'.json'),dict(variant=variant,campaign=campaign,
        physical_interval_s=(FRAMES[[0,-1]]/FS).tolist(),subjects=results,scope='Seven October subjects at their 480 displayed times. '
        'Native and independently integrated coordinates are applied to the same signed native modes. The comparison includes '
        'every stored scalar in the displayed fields. The stress colour scale includes all PCB element corners.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant',choices=['bare','stand3_nylon','stand3_aluminium'])
    p.add_argument('--campaign',default='nov08_01')
    a=p.parse_args()
    run(a.variant,a.campaign)

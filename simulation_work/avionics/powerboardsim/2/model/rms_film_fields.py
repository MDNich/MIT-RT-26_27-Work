"""Recover the one-sigma displacement at each film vertex and compare available native PSD fields."""
import argparse

import numpy as np

from audit_local import ROOT,read
from basis_comparison import field_files
from film_identity import digest,verified,write_json
from independent_psd import moments,rms_field,spectrum_input
from motion_surface import displacement_basis
from native_rst import read_rst
from rms_video import apply_field,surfaces
from seeded_motion import participation
from study_cases import native_case


def locations(meshes):
    return np.unique(np.concatenate([s.point_data['ansys_node_num'] for s,_ in meshes]))


def cache_path(branch,axis,campaign):
    return ROOT/'.runtime/post'/campaign/(branch+'_films')/'independent_RMS'/(axis+'.npz')


def prepare(branch,campaign):
    case=branch+'_basis'
    parent=read(ROOT/'validation/global'/(case+'.json'))
    refpath=ROOT/'validation/independent_psd'/(case+'.json')
    reference=read(refpath)
    assert reference['case']==parent['case']==case and reference['campaign']==parent['campaign']==campaign
    assert reference['baseline_5pct_screen_passed'] and reference['rst_sha256']==parent['rst_sha256']
    vault=ROOT/'.runtime/archive'/campaign/case
    verified(vault/'file.rst',parent['rst_sha256'])
    ledger=read(ROOT/'.runtime/receipts'/campaign/case/'archived.json')
    log=vault/'solve.out'
    log_sha=verified(log,next(v['sha256'] for v in ledger['files'] if v['name']=='solve.out'))
    listing=log.read_text(errors='replace')
    rst=read_rst(vault/'file.rst')
    assert np.array_equal(rst.time_values,parent['frequencies_Hz'])
    ids=locations(surfaces(rst))
    stems=None if branch=='bare' else field_files(case,campaign,parent['rst_sha256'],rst.nsets)
    phi=np.moveaxis(displacement_basis(rst,ids,stems),0,-1)
    for axis in 'XYZ':
        path,f,s,z=spectrum_input(axis)
        prev=reference['base_cases'][axis]
        spectrum_sha=verified(path,prev['spectra_source_sha256'])
        covariance,power=moments(rst.time_values,participation(listing,axis),f,s,z,.125)
        assert abs(np.sqrt(power)-prev['base_RMS_m_s2'])<1e-8
        values=rms_field(phi,covariance)
        sample=phi[::max(1,len(ids)//101)]
        direct=1000*np.sqrt(np.maximum(0.,np.einsum('ijk,kl,ijl->ij',sample,covariance,sample)))
        assert np.allclose(values[::max(1,len(ids)//101)],direct,atol=1e-10,rtol=1e-8)
        target=cache_path(branch,axis,campaign)
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            with np.load(target) as old:
                assert np.array_equal(ids,old['nodes']) and np.allclose(values,old['RMS_mm'],rtol=1e-12,atol=1e-15)
        else:
            temporary=target.with_suffix('.new.npz')
            np.savez_compressed(temporary,nodes=ids,RMS_mm=values)
            temporary.replace(target)
        name=native_case(branch,'psd_'+axis)
        proof=dict(case=name,branch=branch,campaign=campaign,axis=axis,method='Independent PSD integration',
                   basis=case,rst_sha256=parent['rst_sha256'],modal_listing_sha256=log_sha,
                   surface_field_sha256=digest(target),spectrum_sha256=spectrum_sha,independent_reference_sha256=digest(refpath),
                   vertices=len(ids),peak_XYZ_RMS_mm=values.max(0).tolist(),
                   scope='Absolute one-sigma displacement from signed mode shapes, two-percent damping and the original '
                         'single-axis input spectrum. Surface nodes include the beam shanks. Contact state fixed.')
        write_json(ROOT/'validation/rms_film_fields'/(name+'.json'),proof)
        print(branch,axis,len(ids),values.max(0),flush=True)
        if (ROOT/'validation/global'/(name+'.json')).is_file():
            compare_native(branch,axis,campaign)


def compare_native(branch,axis,campaign):
    name=native_case(branch,'psd_'+axis)
    pth=ROOT/'validation/rms_film_fields'/(name+'.json')
    p=read(pth)
    native=read(ROOT/'validation/global'/(name+'.json'))
    assert p['case']==native['case']==name and p['campaign']==native['campaign']==campaign
    src=ROOT/'.runtime/archive'/campaign/name/'file.rst'
    verified(src,native['rst_sha256'])
    cache=cache_path(branch,axis,campaign);verified(cache,p['surface_field_sha256'])
    out=ROOT/'validation/rms_film_checks'/(name+'.json')
    if out.is_file():
        prior=read(out)
        assert prior['native_rst_sha256']==native['rst_sha256'] and prior['independent_source_sha256']==digest(pth)
        if 'maximum_coordinate_difference_m' in prior:return
    rst=read_rst(src)
    node,raw=rst.nodal_solution([3,1]);order=np.argsort(node)
    native_surface=surfaces(rst)
    ids=locations(native_surface)
    basis_path=ROOT/'.runtime/archive'/campaign/p['basis']/'file.rst'
    verified(basis_path,p['rst_sha256'])
    basis=read_rst(basis_path)
    modal_surface=surfaces(basis)
    for (x,opaque_x),(y,opaque_y) in zip(native_surface,modal_surface,strict=True):
        assert opaque_x==opaque_y and np.array_equal(x.faces,y.faces)
        assert np.array_equal(x.point_data['ansys_node_num'],y.point_data['ansys_node_num'])
    pos=rst.mesh.nodes[np.searchsorted(rst.mesh.nnum,ids)]
    ref=basis.mesh.nodes[np.searchsorted(basis.mesh.nnum,ids)]
    coord_err=float(abs(pos-ref).max())
    assert coord_err<1e-9
    with np.load(cache) as data:
        assert np.array_equal(data['nodes'],ids)
        approx=data['RMS_mm']
    idx=order[np.searchsorted(node[order],ids)]
    assert np.array_equal(node[idx],ids)
    actual=1000*np.abs(raw[idx,:3])
    assert np.isfinite(actual).all()
    diff=np.linalg.norm(actual-approx,axis=0)/np.linalg.norm(actual,axis=0)
    peakdiff=np.abs(actual.max(0)-approx.max(0))/actual.max(0)
    assert np.all(diff<.02) and np.all(peakdiff<.02),(diff,peakdiff)
    write_json(out,dict(native_case=name,campaign=campaign,native_rst_sha256=native['rst_sha256'],
        independent_source_sha256=digest(pth),vertices=len(ids),relative_field_L2_XYZ=diff.tolist(),
        relative_surface_peak_error_XYZ=peakdiff.tolist(),native_peak_XYZ_mm=actual.max(0).tolist(),
        maximum_coordinate_difference_m=coord_err,identical_surface_connectivity=True))


def film_field(branch,axis,component,campaign):
    key=native_case(branch,'psd_'+axis)
    p=read(ROOT/'validation/rms_film_fields'/(key+'.json'))
    assert p['branch']==branch and p['axis']==axis and p['campaign']==campaign and p['case']==key
    vault=ROOT/'.runtime/archive'/campaign/p['basis']/'file.rst'
    verified(vault,p['rst_sha256']);cache=cache_path(branch,axis,campaign);verified(cache,p['surface_field_sha256'])
    with np.load(cache) as data:
        actors,peak=apply_field(surfaces(read_rst(vault)),data['nodes'],data['RMS_mm'][:,'XYZ'.index(component)])
    assert abs(peak-p['peak_XYZ_RMS_mm']['XYZ'.index(component)])<1e-12
    return actors,peak,dict(variant=branch,rst_sha256=p['rst_sha256'],surface_field_sha256=p['surface_field_sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('branch',choices=['bare','stand3_nylon','stand3_aluminium'])
    p.add_argument('--campaign',default='nov08_01')
    args=p.parse_args();prepare(args.branch,args.campaign)

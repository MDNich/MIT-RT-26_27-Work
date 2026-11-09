"""Recover whole-cell forces from native modal coordinates and verify the independent seeded result."""
import argparse
import re
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

from audit_local import ROOT,read
from film_identity import digest,verified,write_json
from motion_surface import displacement_basis
from native_rst import read_rst
from seeded_motion import FRAMES,FS,excitation,participation


def from_coordinates(coordinates,mean,frequencies,gamma,axis):
    t,base,_=excitation(axis)
    assert coordinates.shape==(len(t),len(frequencies))
    # Average-acceleration Newmark enforces the trapezoidal velocity update.
    # Recover velocity from the modal equilibrium without differentiating the
    # rounded displacements twice.
    dt=1/FS
    absolute=base[:,None,None]*np.tile(np.eye(3)['XYZ'.index(axis)],(len(mean),1))[None,:,:]
    for j,(freq,g) in enumerate(zip(frequencies,gamma,strict=True)):
        omega=2*np.pi*freq
        damping=.04*omega
        force=-g*base-omega**2*coordinates[:,j]
        denom=1+.5*dt*damping
        velocity=lfilter([.5*dt/denom,.5*dt/denom],[1.,-(1-.5*dt*damping)/denom],force)
        accel=force-damping*velocity
        absolute+=accel[:,None,None]*mean[None,:,:,j]
    return np.sqrt(np.mean(absolute[FS:-1]**2,axis=0))/9.806


def compare(data,reference,axis):
    expected=np.array([v['seed_mean_acceleration_XYZ_rms_g'] for v in reference['base_cases'][axis]['cells'].values()])
    error=abs(data/expected-1)
    assert np.max(error)<.001,error
    return dict(mean_acceleration_XYZ_rms_g=data.tolist(),relative_errors=error.tolist())


def repeat(branch,campaign,axis,coordinates,basis_sha,listing):
    reference=ROOT/'validation/cell_force'/(branch+'.json')
    record=read(reference)
    assert record['basis_rst_sha256']==basis_sha and record['campaign']==campaign
    cache=ROOT/'.runtime/post'/campaign/(branch+'_basis')/'cell_mass_mean.npz'
    verified(cache,record['mean_shapes_sha256'])
    with np.load(cache) as d:
        observed=from_coordinates(coordinates,d['mean'],d['frequencies_Hz'],participation(listing,axis),axis)
        assert list(d['materials'])==list(map(int,record['geometry']))
    return dict(independent_result_sha256=digest(reference),**compare(observed,record,axis))


def october(archive,campaign):
    from audit_motion import full_history
    source=archive/'outputs/random_motion_20261005_2143'
    modal=archive/'outputs/random_vibration_20261005_0950/modal_basis'
    src=modal/'file.rst'
    old_sha=read(ROOT/'validation/pcb_dynamic_stress_reader.json')['rst_sha256']
    verified(src,old_sha)
    old=read_rst(src)
    ref=read(ROOT/'validation/cell_force/bare.json')
    cache=ROOT/'.runtime/post'/campaign/'bare_basis/cell_mass_weights.npz'
    verified(cache,ref['mass_weights_sha256'])
    gen=ROOT/'.runtime/archive'/campaign/'bare_basis/file.rst'
    verified(gen,ref['basis_rst_sha256']);new=read_rst(gen)
    with np.load(cache) as w:
        ids=w['nodes'];weights=w['weights']; materials=w['materials']
    for r in (old,new):
        i=np.searchsorted(r.mesh.nnum,ids);assert np.array_equal(r.mesh.nnum[i],ids)
    assert np.max(abs(old.mesh.nodes[np.searchsorted(old.mesh.nnum,ids)]-new.mesh.nodes[np.searchsorted(new.mesh.nnum,ids)]))<1e-9
    def topology(r):
        g=r.grid.cell_data
        elements=np.sort(g['ansys_elem_num'][np.isin(g['ansys_material_type'],materials)&(g['ansys_elem_type_num']==187)])
        idx=np.argsort(r.mesh.enum);raw=r.mesh.elem
        return np.stack([raw[n][8:] for n in idx[np.searchsorted(r.mesh.enum[idx],elements)]])
    assert np.array_equal(topology(old),topology(new))
    shapes=displacement_basis(old,ids)
    mean=np.einsum('cn,mnj->cjm',weights,shapes,optimize=True)
    listing=(modal/'solve.out').read_text(errors='replace')
    all_checks={}
    for axis in 'XYZ':
        folder=source/('transient_'+axis)
        mcf=folder/'file.mcf'
        log=(folder/'solve.out').read_text(errors='replace')
        assert 'RUN COMPLETED' in log and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',log)
        q,metrics=full_history(mcf,old.time_values,listing,axis)
        table=ROOT.parent/'1/output/latex/random_vibration/reproduction/motion/inputs'/f'modal_coordinates_{axis}_clip.csv'
        known=np.loadtxt(table,delimiter=',',skiprows=1)
        assert np.array_equal(q[FRAMES],known[:,1:])
        observed=from_coordinates(q,mean,old.time_values,participation(listing,axis),axis)
        rec=compare(observed,ref,axis)
        all_checks[axis]=dict(**rec,mcf_sha256=digest(mcf),listing_sha256=digest(folder/'solve.out'),
                              clip_csv_sha256=digest(table),full_history_relative_L2=metrics['full_history_relative_L2'])
        print(axis,np.max(rec['relative_errors']),flush=True)
    write_json(ROOT/'validation/cell_force/october_native_history.json',dict(campaign=campaign,old_basis_sha256=old_sha,
        old_basis_listing_sha256=digest(modal/'solve.out'),new_independent_result_sha256=digest(ROOT/'validation/cell_force/bare.json'),
        cells=list(map(int,materials)),base_cases=all_checks,scope='Original native modal coordinate histories and original '
        'signed mode shapes. Absolute acceleration reconstructed by modal equilibrium and the Newmark velocity update.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('october_archive',type=Path)
    p.add_argument('--campaign',default='nov08_01')
    args=p.parse_args();october(args.october_archive,args.campaign)

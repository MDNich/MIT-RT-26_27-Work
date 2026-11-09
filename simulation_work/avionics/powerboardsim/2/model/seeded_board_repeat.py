"""Compare physical motion from the fresh bare eigenbasis to the archived October clip."""
import argparse
import csv

import numpy as np

from audit_local import ROOT,read
from film_identity import digest,verified,write_json
from motion_surface import displacement_basis
from native_rst import read_rst
from pcb_dynamic_stress import cache_modes,extrema
from seeded_motion import FS,FRAMES,integrate,participation


def check(campaign,*,native=False):
    case='bare_basis';p=read(ROOT/'validation/global/bare_basis.json')
    assert p['case']==case and p['campaign']==campaign
    folder=ROOT/'.runtime/archive'/campaign/case
    inputs=read(ROOT/'.runtime/receipts'/campaign/case/'archived.json')
    verified(folder/'file.rst',p['rst_sha256'])
    verified(folder/'solve.out',next(r['sha256'] for r in inputs['files'] if r['name']=='solve.out'))
    listing=(folder/'solve.out').read_text(errors='replace')
    r=read_rst(folder/'file.rst')
    cache=ROOT/'.runtime/post'/campaign/'bare_films/pcb_stress'
    meta=cache_modes(folder/'file.rst',cache);assert meta['rst_sha256']==p['rst_sha256']
    source=ROOT.parent/'1/output/latex/random_vibration/reproduction/motion'
    record={}
    for axis in 'XYZ':
        file=source/f'native/expand_{axis}/native_node_checks.csv'
        hist=np.genfromtxt(file,delimiter=',',names=True)
        ids=np.unique(hist['node'].astype(int));phi=displacement_basis(r,ids)
        if native:
            key='bare_motion_'+axis
            proof=read(ROOT/'validation/motion'/f'{key}.json')
            assert proof['basis_rst_sha256']==p['rst_sha256'] and proof['campaign']==campaign
            path=ROOT/'.runtime/post'/campaign/key/'coordinates.npz';verified(path,proof['clip_sha256'])
            with np.load(path) as clip:
                assert np.array_equal(clip['frequencies_Hz'],r.time_values)
                t,q=clip['time_s'],clip['coordinates']
        else:
            t,q,_=integrate(r.time_values,participation(listing,axis),axis)
        assert q.shape==(480,r.nsets) and np.array_equal(t,FRAMES/FS)
        u=(q@phi.reshape(r.nsets,-1)).reshape(len(t),len(ids),3)
        frames=hist['set'].astype(int)-1;nodes=np.searchsorted(ids,hist['node'])
        old=np.column_stack([hist['u'+a] for a in 'xyz'])
        assert np.allclose(t[frames],hist['time'],atol=1e-10,rtol=0)
        diff=u[frames,nodes]-old
        rel=float(np.linalg.norm(diff)/np.linalg.norm(old))
        assert rel<.001,rel
        data=dict(October_mapdl_sha256=digest(file),checked_frames=(np.unique(frames)+1).tolist(),
                  checked_nodes=ids.tolist(),relative_displacement_L2=rel,max_abs_displacement_error_m=float(np.abs(diff).max()))
        if native:data['native_coordinates_sha256']=proof['clip_sha256']
        if axis=='X':
            points=source/'audits/dpf_stress_unaveraged_frames.json';dpf=read(points)
            assert [x['frame'] for x in dpf]==list(range(1,481))
            signed=np.array([[s['u_nodes'][str(n)] for n in ids] for s in dpf])
            smin,smax=extrema(np.load(cache/'tensors.npy',mmap_mode='r'),q)
            maxima=np.array([row['maximum_Pa'] for row in dpf]);minima=np.array([row['minimum_Pa'] for row in dpf])
            dev=float(abs(smax/maxima-1).max())
            assert dev<.001 and np.linalg.norm(u-signed)/np.linalg.norm(signed)<.001
            data.update(October_DPF_sha256=digest(points),stress_frames=480,native_element_corner_records=meta['element_corner_records'],
                        peak_dynamic_von_Mises_MPa=float(smax.max()*1e-6),largest_frame_peak_relative_difference=dev,
                        largest_absolute_minimum_difference_Pa=float(abs(smin-minima).max()),
                        all_frames_signed_displacement_relative_L2=float(np.linalg.norm(u-signed)/np.linalg.norm(signed)))
        record[axis]=data
    method='native' if native else 'independent'
    write_json(ROOT/'validation'/f'seeded_bare_{method}_repeat.json',dict(method=method,campaign=campaign,
        basis_rst_sha256=p['rst_sha256'],axes=record,
        scope='Fresh original-board signed native modes and stress tensors with '+method+
              ' modal coordinates, compared against October physical translations and unaveraged PCB stress extrema.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('campaign');parser.add_argument('--native',action='store_true')
    args=parser.parse_args();check(args.campaign,native=args.native)

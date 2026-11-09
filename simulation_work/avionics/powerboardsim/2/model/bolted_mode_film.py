"""Match the original bolted mode 20 to the raised assemblies using the accepted native mode sets."""
import argparse

import numpy as np

from audit_local import ROOT,read
from basis_comparison import field_files
from film_identity import verified,write_json
from modal_correspondence import reference_geometry
from native_rst import read_rst


def vector(rst,ids,k,fields):
    if fields is None:
        node,u=rst.nodal_displacement(k)
    else:
        stem=fields[k+1]
        node=np.fromfile(stem.with_suffix('.ids'),'<i4')
        u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
    order=np.argsort(node)
    sel=order[np.searchsorted(node[order],ids)]
    assert np.array_equal(node[sel],ids)
    v=np.ascontiguousarray(u[sel,:3]).ravel()
    norm=np.linalg.norm(v)
    assert np.isfinite(norm) and norm>0
    return v/norm


def run(campaign):
    rank=20
    def source(name):
        p=read(ROOT/'validation/global'/(name+'.json'))
        assert p['case']==name and p['campaign']==campaign
        path=ROOT/'.runtime/archive'/campaign/name/'file.rst'
        verified(path,p['rst_sha256'])
        return read_rst(path),p['rst_sha256']
    bare,base_sha=source('bare_modal20')
    ids,xyz,pose=reference_geometry(bare)
    ref=vector(bare,ids,rank-1,None)
    results={}
    for branch in ['bare','stand3_nylon','stand3_aluminium']:
        key=branch+'_basis'
        r,sha=source(key)
        numbers,base,p=reference_geometry(r)
        assert np.array_equal(numbers,ids) and np.max(abs(xyz-base))<1e-9
        fields=None if branch=='bare' else field_files(key,campaign,sha,r.nsets)
        scores=np.array([np.clip(np.dot(ref,vector(r,ids,k,fields)),-1.,1.) for k in range(r.nsets)])
        mac=scores**2
        order=np.argsort(mac)[::-1]
        record=dict(variant=branch,case=key,rst_sha256=sha,rank=rank,Hz=float(r.time_values[rank-1]),
                    same_rank_MAC=float(mac[rank-1]),phase_sign=int(np.sign(scores[rank-1])) or 1,
                    closest_shape_rank=int(order[0])+1,closest_shape_Hz=float(r.time_values[order[0]]),
                    closest_MAC=float(mac[order[0]]),runner_up_MAC=float(mac[order[1]]),modes_searched=r.nsets,
                    static_pose=p,MAC_by_rank=mac.tolist())
        if branch=='bare':
            assert record['closest_shape_rank']==rank and record['same_rank_MAC']>.9999
            assert abs(record['Hz']/bare.time_values[rank-1]-1)<1e-5
        results[branch]=record
        print(branch,record['Hz'],record['same_rank_MAC'],record['closest_shape_rank'],record['closest_MAC'],flush=True)
    write_json(ROOT/'validation/bolted_mode_film.json',dict(campaign=campaign,reference_case='bare_modal20',
        reference_rst_sha256=base_sha,reference_Hz=float(bare.time_values[rank-1]),common_solid_nodes=len(ids),
        reference_static_pose=pose,cases=results,scope='Mass-normalized native eigenvectors compared with the '
        'original 20-mode repeat using the three translations of each common solid node. Reported MAC is '
        'the squared unweighted normalized dot product. Phase sign aligns the displayed rank-20 eigenvector.'))


def confirm_dedicated(branch,campaign,former,replacement,rank):
    """Check that the dedicated extraction preserves the displayed physical shape before replacement."""
    keys=[branch+'_basis',branch+'_modal20']
    modes=[]
    for key,expected in zip(keys,[former,replacement],strict=True):
        source=ROOT/'.runtime/archive'/campaign/key/'file.rst'
        proof=read(ROOT/'validation/global'/(key+'.json'))
        assert proof['case']==key and proof['campaign']==campaign and proof['rst_sha256']==expected
        verified(source,expected);modes.append(read_rst(source))
    (ids,a,_),(matched,b,_)=[reference_geometry(r,include_case=True) for r in modes]
    assert np.array_equal(ids,matched) and np.max(abs(a-b))<1e-9
    src=field_files(keys[0],campaign,former,modes[0].nsets)
    x=vector(modes[0],ids,rank-1,src);y=vector(modes[1],ids,rank-1,None)
    mac=float(np.clip(x@y,-1,1)**2)
    freq=[float(r.time_values[rank-1]) for r in modes]
    assert mac>.999 and abs(freq[1]/freq[0]-1)<1e-5
    write_json(ROOT/'validation/modal_matches'/(branch+'_wide_to_dedicated.json'),
               dict(rank=rank,wide_rst_sha256=former,dedicated_rst_sha256=replacement,
                    case_and_original_solid_nodes=len(ids),frequencies_Hz=freq,MAC=mac))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign',default='nov08_01')
    run(p.parse_args().campaign)

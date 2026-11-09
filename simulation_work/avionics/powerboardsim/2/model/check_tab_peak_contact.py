"""Check the actual cell and PLA triangulations at the predicted peak layer-normal tension."""
import argparse

import numpy as np

from audit_local import ROOT,read
from basis_comparison import field_files
from clearance_response import surface
from film_identity import digest,verified,write_json
from native_rst import read_rst
from seeded_motion import FS,integrate,participation


def check(variant,campaign):
    spectrum=variant+'_psd_X_private1'
    field=read(ROOT/'validation/pla_stress'/f'{spectrum}.json')
    peak=field['independent_signed_waveform']['maximum']
    step=round(peak['time_s']*FS);assert abs(step/FS-peak['time_s'])<1e-12
    key=variant+'_basis';src=ROOT/'.runtime/archive'/campaign/key
    p=read(ROOT/'validation/global'/f'{key}.json')
    assert p['rst_sha256']==field['basis_sha256'] and p['campaign']==field['campaign']==campaign
    path=src/'file.rst';verified(path,p['rst_sha256'])
    log=src/'solve.out';ledger=read(ROOT/'.runtime/receipts'/campaign/key/'archived.json')
    verified(log,next(row['sha256'] for row in ledger['files'] if row['name']=='solve.out'))
    r=read_rst(path);t,q,_=integrate(r.time_values,participation(log.read_text(errors='replace'),'X'), 'X',np.array([step]))
    records=field_files(key,campaign,p['rst_sha256'],r.nsets)
    shapes=[surface(r,m) for m in ([850],[176,187,191])]
    ids=np.unique(np.concatenate([s[2] for s in shapes]));u=np.zeros((len(ids),3))
    for k,w in enumerate(q[0],1):
        stem=records[k];n=np.fromfile(stem.with_suffix('.ids'),'<i4');v=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
        order=np.argsort(n);ix=order[np.searchsorted(n[order],ids)];assert np.array_equal(n[ix],ids)
        u+=w*v[ix]
    def collision(displacement):
        skins=[]
        for s,faces,n,normals in shapes:
            mesh=s.copy();mesh.points=s.points+displacement[np.searchsorted(ids,n)]
            assert mesh.n_open_edges==0
            skins.append(mesh)
        cap,cells=skins
        _,count=cap.collision(cells,contact_mode=0,box_tolerance=0.,cell_tolerance=0.)
        distance=cells.compute_implicit_distance(cap).point_data['implicit_distance']
        return dict(intersecting_triangle_pairs=int(count),cell_vertices_over_1um_inside=int((distance< -1e-6).sum()),
                    deepest_sampled_cell_vertex_mm=float(max(0.,-distance.min())*1000))
    before=collision(np.zeros_like(u));assert before['intersecting_triangle_pairs']==before['cell_vertices_over_1um_inside']==0
    result=dict(case=spectrum,campaign=campaign,basis_sha256=p['rst_sha256'],layer_field_sha256=digest(ROOT/'validation/pla_stress'/f'{spectrum}.json'),
        sample=step,time_s=float(t[0]),conditional_peak_tension_MPa=peak['stress_MPa'],locked=before,peak=collision(u),
        scope='Single physical-time sample at the printed tab stress maximum in the independent signed linear solution. Surface overlap tests the assumed open contact state.')
    write_json(ROOT/'validation/peak_contact'/f'{variant}.json',result)
    print(variant,result['peak'])
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('variant');a.add_argument('campaign')
    q=a.parse_args();check(q.variant,q.campaign)

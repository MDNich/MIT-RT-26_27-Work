"""Compare the first sampled outer-pocket intersections with identical forcing on two case meshes."""
import argparse

import numpy as np

from audit_local import read
from film_identity import digest, write_json
from stage_snug_fit import AUDIT, STEP_HASH


def compare(material):
    modal=AUDIT/(material+'_modal_mesh_comparison.json')
    models=read(modal)['models']
    assert [m['mesh_size_mm'] for m in models]==[2,1.5]
    result=[]
    for model in models:
        variant=model['case'].removesuffix('_basis')
        installed_path=AUDIT/(model['preload']+'_contacts.json')
        installed=read(installed_path)
        assert installed['case_mesh_sha256']==model['mesh_sha256'] and installed['step_sha256']==STEP_HASH
        assert installed['rst_sha256']==model['installed_rst_sha256']
        path=AUDIT/(variant+'_outer_onset_Z_exact.json')
        geometry=read(path)
        cert=path.with_name(path.stem+'_witness.json');witness=read(cert)
        assert geometry['basis_rst_sha256']==model['basis_rst_sha256'] and witness['source_sha256']==digest(path)
        assert geometry['base_axis']=='Z' and geometry['method']==witness['method']=='exact'
        assert witness['variant']==geometry['variant']==variant
        cells={}
        for side,body in [('left',4),('right',15)]:
            bounds=geometry['cells'][side];point=witness['cells'][side]
            assert not bounds['unresolved_samples'] and bounds['last_contiguous_clear_sample']+1==bounds['first_intersecting_sample']
            low=bounds['last_contiguous_clear_sample'];high=point['sample']
            assert low<high and abs(np.sum(point['PLA_barycentric'])-1)<1e-10
            assert point['residual_mm']<1e-9 and point['normal_cross_magnitude']>1e-5
            interval=np.array([low,high])*1000/geometry['sample_rate_Hz']
            assert np.array_equal(interval,point['first_intersection_interval_ms'])
            gap,=[r for r in installed['locked_geometry']['rows'] if r['body']==body and r['subdivision']==3]
            assert not gap['intersects']
            cells[side]=dict(sample_interval=[low,high],time_interval_ms=interval.tolist(),
                             sampled_locked_gap_um=1000*gap['minimum_signed_target_vertex_gap_mm'],
                             witness_xyz_mm=point['quadratic_point_xyz_mm'])
        order=sorted(cells,key=lambda side:cells[side]['sample_interval'][0])
        assert cells[order[0]]['sample_interval'][1]<cells[order[1]]['sample_interval'][0]
        result.append(dict(variant=variant,mesh_mm=model['mesh_size_mm'],mesh_sha256=model['mesh_sha256'],
                           basis_sha256=model['basis_rst_sha256'],waveform_sha256=geometry['input_sha256'],
                           sample_rate_Hz=geometry['sample_rate_Hz'],face_counts=geometry['quadratic_face_counts'],
                           installed_sha256=digest(installed_path),witness_sha256=digest(cert),order=order,cells=cells))
    a,b=result
    assert a['waveform_sha256']==b['waveform_sha256'] and a['sample_rate_Hz']==b['sample_rate_Hz']
    assert a['face_counts'][1:]==b['face_counts'][1:] and b['face_counts'][0]>a['face_counts'][0]
    delta={}
    for side in a['cells']:
        lo,hi=a['cells'][side]['time_interval_ms']
        fine_lo,fine_hi=b['cells'][side]['time_interval_ms']
        delta[side]=dict(fine_minus_nominal_midpoint_ms=(fine_lo+fine_hi-lo-hi)/2,
                         possible_fine_minus_nominal_ms=[fine_lo-hi,fine_hi-lo])
    write_json(AUDIT/(material+'_outer_startup_mesh_comparison.json'),dict(models=result,interval_changes=delta,
               order_retained=a['order']==b['order'],modal_comparison_sha256=digest(modal),
               scope='Sampled fixed-contact trajectories from independent exact integration of each native mode basis. '
                     'Interval differences reflect the two tested meshes. A face-intersection witness does not determine '
                     'a unique physical impact point or the amount of contact pressure.'))
    print(material,a['order'],b['order'],delta)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('material',choices=('nylon','aluminium'))
    compare(p.parse_args().material)

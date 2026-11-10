"""Compare the first sampled outer-pocket intersections with identical forcing on two case meshes."""
import argparse

import numpy as np

from audit_local import read
from film_identity import digest, write_json
from stage_snug_fit import AUDIT, STEP_HASH


def compare(material,axis='Z',*,coarse=False):
    modal=AUDIT/(material+'_modal_mesh_comparison.json')
    models=read(modal)['models']
    assert [m['mesh_size_mm'] for m in models]==[2,1.5]
    additional={}
    if coarse:
        assert material=='nylon'
        setup_file=AUDIT/'coarse_geometry_modes.json';setup=read(setup_file)
        proof_file=AUDIT/'coarse_geometry_modes_audit.json';proof=read(proof_file)
        assert proof['registry_sha256']==digest(setup_file) and proof['case']==setup['case']
        assert proof['matching']['reference_rst_sha256']==models[0]['basis_rst_sha256']
        assert setup['reference']==models[0]['case']
        models=[dict(case=setup['case'],preload=setup['parent'],mesh_sha256=setup['mesh_sha256'],
                     installed_rst_sha256=setup['static_rst_sha256'],mesh_size_mm=setup['size_mm'],
                     basis_rst_sha256=proof['matching']['candidate_rst_sha256']),models[0]]
        additional['coarse_displacement_audit_sha256']=digest(proof_file)
    result=[]
    for model in models:
        variant=model['case'].removesuffix('_basis')
        installed_path=AUDIT/(model['preload']+'_contacts.json')
        installed=read(installed_path)
        assert installed['case_mesh_sha256']==model['mesh_sha256'] and installed['step_sha256']==STEP_HASH
        assert installed['rst_sha256']==model['installed_rst_sha256']
        path=AUDIT/(f'{variant}_outer_onset_{axis}_exact.json')
        geometry=read(path)
        cert=path.with_name(path.stem+'_witness.json');witness=read(cert)
        assert geometry['basis_rst_sha256']==model['basis_rst_sha256'] and witness['source_sha256']==digest(path)
        assert geometry['base_axis']==axis and geometry['method']==witness['method']=='exact'
        assert witness['variant']==geometry['variant']==variant
        cells={}
        for side,body in [('left',4),('right',15)]:
            bounds=geometry['cells'][side];point=witness['cells'][side]
            unresolved=bounds['unresolved_samples'];first=bounds['first_intersecting_sample']
            assert first is not None and bounds['last_contiguous_clear_sample']+1==min([first,*unresolved])
            assert all(bounds['last_contiguous_clear_sample']<k<first for k in unresolved)
            low=bounds['last_contiguous_clear_sample'];high=point['sample']
            assert low<first<=high<geometry['samples']
            assert all(abs(np.sum(point[key+'_barycentric'])-1)<1e-10 for key in ('PLA','cell'))
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
    suffix='' if axis=='Z' else '_'+axis
    if coarse:
        suffix='_3_to_2mm_'+axis
        delta={side:dict(nominal_minus_coarse_midpoint_ms=d['fine_minus_nominal_midpoint_ms'],
                         possible_nominal_minus_coarse_ms=d['possible_fine_minus_nominal_ms']) for side,d in delta.items()}
    write_json(AUDIT/(material+'_outer_startup_mesh_comparison'+suffix+'.json'),dict(**additional,models=result,interval_changes=delta,
               order_retained=a['order']==b['order'],modal_comparison_sha256=digest(modal),
               scope='Sampled fixed-contact trajectories from independent exact integration of each native mode basis. '
                     'Interval differences reflect the two tested meshes. A face-intersection witness does not determine '
                     'a unique physical impact point or the amount of contact pressure.'))
    print(material,a['order'],b['order'],delta)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('material',choices=('nylon','aluminium'))
    p.add_argument('--axis',choices=('X','Y','Z'),default='Z')
    p.add_argument('--coarse',action='store_true',help='Compare the 3 and 2 mm cases.')
    args=p.parse_args();compare(args.material,args.axis,coarse=args.coarse)

"""Cross-check both outer cells under each base axis on native and independently integrated trajectories."""
from audit_local import read
from film_identity import digest,write_json
from stage_snug_fit import AUDIT


def compare(axis,variant):
    tables=[];sources={};intervals={}
    for method in ('native','exact'):
        p=AUDIT/f'{variant}_outer_onset_{axis}_{method}.json'
        w=p.with_name(p.stem+'_witness.json')
        scan,witness=read(p),read(w)
        assert scan['variant']==witness['variant']==variant and scan['base_axis']==axis
        assert scan['method']==witness['method']==method and witness['source_sha256']==digest(p)
        sources[method]=dict(scan=digest(p),witness=digest(w))
        ranges={}
        for side in ('left','right'):
            c=scan['cells'][side];proof=witness['cells'][side]
            lo=c['last_contiguous_clear_sample'];hi=proof['sample'];rate=scan['sample_rate_Hz']
            assert 0<=lo<c['first_intersecting_sample']<=hi<scan['samples']
            assert proof['first_intersection_interval_ms']==[1000*lo/rate,1000*hi/rate]
            assert proof['residual_mm']<1e-9 and proof['normal_cross_magnitude']>1e-5
            ranges[side]=[lo,hi]
        intervals[method]=ranges;tables.append(scan)
    n,e=tables
    for key in ('basis_rst_sha256','input_sha256','campaign','samples','sample_rate_Hz','quadratic_face_counts'):
        assert n[key]==e[key]
    order={};both={}
    for method,r in intervals.items():
        first,last=sorted(r,key=lambda side:r[side][0])
        assert r[first][1]<r[last][0]
        order[method]=[first,last]
    for side in ('left','right'):
        a=intervals['native'][side];b=intervals['exact'][side]
        both[side]=dict(native_bracket_samples=a,independent_bracket_samples=b,
                        largest_endpoint_shift_samples=max(abs(x-y) for x,y in zip(a,b,strict=True)),
                        bounds_jointly_cover_ms=[1000*min(a[0],b[0])/n['sample_rate_Hz'],1000*max(a[1],b[1])/n['sample_rate_Hz']])
    return dict(sources=sources,order=order,same_order=order['native']==order['exact'],cells=both)


if __name__=='__main__':
    axes={axis:{s:compare(axis,'snug125_'+s) for s in ('nylon','aluminium')} for axis in 'XYZ'}
    write_json(AUDIT/'outer_startup_axis_comparison.json',dict(axes=axes,
               scope='First confirmed transverse intersections after contiguous clear samples, on the nominal '
                     'native motion histories and the same modes integrated independently with linearly interpolated input.'))

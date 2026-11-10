"""Compare nickel trial stress, middle-pocket unloading bounds and first outer-pocket geometry on matched meshes."""
import argparse
from audit_local import read
from film_identity import digest,write_json
from stage_snug_fit import AUDIT


def interval_difference(a,b):
    return [a[0]-b[1],a[1]-b[0]]


def compare(axis):
    mesh_path=AUDIT/('nylon_outer_startup_mesh_comparison'+('' if axis=='Z' else '_'+axis)+'.json')
    stress_path=AUDIT/f'nylon_nickel_startup_mesh_{axis}.json'
    geometry,stress=read(mesh_path),read(stress_path)
    assert stress['axis']==axis and stress['modal_comparison_sha256']==geometry['modal_comparison_sha256']
    models=[]
    for contact,nickel in zip(geometry['models'],stress['models'],strict=True):
        branch=contact['variant'];scope=branch.removeprefix('snug125_')
        assert branch==nickel['variant'] and contact['basis_sha256']==nickel['basis_sha256']
        assert contact['waveform_sha256']==stress['input_sha256']
        load_path=AUDIT/(scope+'_pocket_preload.json');load=read(load_path)
        assert load['modal_rst_sha256']==contact['basis_sha256']
        bounds=load['axes'][axis];rate=contact['sample_rate_Hz']
        assert bounds['excitation_sha256']==stress['input_sha256'] and rate==stress['sample_rate_Hz']
        pressure=bounds['integrations']['exact'];latest=pressure['sign_independent_latest_sample']
        assert latest==max(pressure[s]['sample'] for s in ('negative','positive'))
        first=contact['order'][0];outer=contact['cells'][first]['time_interval_ms']
        trial=nickel['events']['4000']['first_crossing']
        assert trial is not None
        y=[1000*t for t in trial['time_bracket_s']]
        dif=interval_difference(y,outer)
        relative='outer first' if dif[0]>0 else ('nickel first' if dif[1]<0 else 'unresolved')
        models.append(dict(variant=branch,mesh_mm=nickel['mesh_mm'],basis_sha256=nickel['basis_sha256'],
                 outer_brackets_ms={s:c['time_interval_ms'] for s,c in contact['cells'].items()},
                 first_outer=first,trial_yield_bracket_ms=y,trial_STEP_body=trial['STEP_body'],
                 trial_minus_first_outer_ms=dif,order=relative,pressure_redistribution_by_ms=1000*latest/rate,
                 both_after_middle_bound=min(y[0],outer[0])>1000*latest/rate,pocket_source_sha256=digest(load_path)))
    result=dict(axis=axis,geometry_mesh_sha256=digest(mesh_path),nickel_mesh_sha256=digest(stress_path),
                models=models,order_retained=models[0]['order']==models[1]['order'],
                scope='Independent integration of the same acceleration table on each installed native basis. '
                      'Contact redistribution at the middle pocket precedes the reported geometric crossings '
                      'when indicated. The signed elastic trial stress does not identify plastic damage.')
    write_json(AUDIT/f'nylon_event_order_mesh_{axis}.json',result)
    print(axis,[(m['order'],m['trial_minus_first_outer_ms']) for m in models])
    return result


def check_cutoff(axis):
    baseline=AUDIT/f'nylon_event_order_mesh_{axis}.json'
    original=read(baseline);stress_path=AUDIT/f'nylon_nickel_startup_mesh_{axis}.json'
    assert original['nickel_mesh_sha256']==digest(stress_path)
    stress=read(stress_path)
    summary=[]
    for model,elastic in zip(original['models'],stress['models'],strict=True):
        assert model['variant']==elastic['variant']
        intervals={};sources={}
        for cutoff,suffix in [('4000',''),('3500','_3500Hz')]:
            stem=f"{model['variant']}_outer_onset_{axis}_exact{suffix}"
            inp=AUDIT/(stem+'.json');w=inp.with_name(stem+'_witness.json')
            scan,hit=read(inp),read(w)
            assert hit['source_sha256']==digest(inp) and scan['base_axis']==axis
            assert scan['method']==hit['method']=='exact' and scan['variant']==hit['variant']==model['variant']
            assert scan['basis_rst_sha256']==elastic['basis_sha256'] and scan['input_sha256']==stress['input_sha256']
            if suffix:
                for key in ('cutoff_Hz','retained_modes','available_modes'):assert hit[key]==scan[key]
                assert scan['cutoff_Hz']==3500 and scan['retained_modes']==elastic['events'][cutoff]['modes']
                assert scan['available_modes']==elastic['events']['4000']['modes']
            values={}
            for side in ('left','right'):
                event=hit['cells'][side]
                l,h=event['first_intersection_interval_ms']
                assert l==1000*scan['cells'][side]['last_contiguous_clear_sample']/scan['sample_rate_Hz']
                assert h==1000*event['sample']/scan['sample_rate_Hz'] and l<h
                assert event['residual_mm']<1e-9 and event['normal_cross_magnitude']>1e-5
                values[side]=[l,h]
            if not suffix:assert values==model['outer_brackets_ms']
            intervals[cutoff]=values;sources[cutoff]=dict(scan_sha256=digest(inp),witness_sha256=digest(w))
        summary.append(dict(variant=model['variant'],identical_pocket_brackets=intervals['4000']==intervals['3500'],
                            intervals_ms=intervals,sources=sources))
    write_json(AUDIT/f'nylon_{axis}_cutoff_pocket_comparison.json',dict(axis=axis,baseline_sha256=digest(baseline),models=summary))
    print(axis,[(r['variant'],r['identical_pocket_brackets']) for r in summary])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('axis',choices=('X','Y','Z'));p.add_argument('--cutoff-check',action='store_true')
    args=p.parse_args()
    if args.cutoff_check:check_cutoff(args.axis)
    else:compare(args.axis)

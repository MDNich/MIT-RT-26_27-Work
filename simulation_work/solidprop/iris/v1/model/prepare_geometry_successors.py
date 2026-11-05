"""Prepare fresh geometry-consistent inputs after the full control passes.

This program never launches or resumes a solver and never edits a sealed parent.
Preparation and campaign activation are separate reviewable operations.
"""
import argparse
import copy
import hashlib
import json
import subprocess
import sys
from ops import ROOT, TMP, atomic, disks, guest, utc
from validate_run import validate
from compare_native_resolution import summary, configuration_descriptor, configuration_comparison
from check_sector_geometry_measures import geometry_audit

CONTROL = 'sustainer_al_pulse7_midpoint_space160_geom005_smp10'
OLD_CONTROL = 'sustainer_al_pulse7_midpoint_space160_smp10'
RECORD = ROOT/'validation/native_geometry_successor_plan.json'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory():
    campaign=read(ROOT/'configs/campaign_queue.json')
    resolution=read(ROOT/'validation/native_resolution_plan.json')
    parents=[r['runtime'] for r in resolution['cases'] if r['level']!='time_quarter']
    parents+=campaign['deferred_sensitivity_runtimes']+campaign['deferred_cutoff_runtimes']
    assert len(parents)==14 and len(set(parents))==14
    assert OLD_CONTROL in parents and all(n.endswith('_smp10') and '_geom005_' not in n for n in parents)
    return {n:n.removesuffix('_smp10')+'_geom005_smp10' for n in parents}


def proposed(parent_name,name):
    parent=TMP/'runs'/parent_name
    cfg=copy.deepcopy(read(parent/'config.json'))
    assert cfg['ranks']==10 and cfg['parallel_mode']=='smp'
    cfg.update(windows_root='C:\\IrisStudy\\runs\\'+name,
               host_runtime='I:\\ansystmp\\runs\\'+name,
               mesh_measure_convention='straight_sided_hex')
    cfg['geometry']['angle_deg']=.05
    cfg['geometry']['full_ring_scale_factor']=7200.
    cfg['numerics']['native_heat_flow_tolerance']=1e-7
    cfg['provenance']['geometry_consistency_parent']=dict(
        runtime=parent_name,config_sha256=sha(parent/'config.json'),control=CONTROL,
        change='Fresh 0.05-degree sector with exact straight-sided mesh measures and 1e-7 heat-flow convergence. Same radial/axial subdivisions, time schedule, physical model and removal rule as this parent.',
        qualification='No inherited native solution. Compare each case with its own unchanged cylindrical reference. Differences from older arc-measure results include geometry and solver changes.')
    return cfg


def terminal_control():
    """A prefix, a completed solve alone or an unmatched comparison cannot pass."""
    runtime=TMP/'runs'/CONTROL
    accepted_path=ROOT/'validation'/f'accepted_{CONTROL}.json'
    comparison_path=ROOT/'validation'/f'native_pulse_comparison_{CONTROL}.json'
    assert read(runtime/'state.json')['status']=='COMPLETED_HORIZON', 'Geometry control has not completed'
    assert accepted_path.exists() and comparison_path.exists(), 'Wait for terminal observer audits'
    accepted=read(accepted_path);checked=validate(runtime)
    assert accepted==checked, 'Terminal audit changed'
    fine=summary(CONTROL)
    coarse=summary('sustainer_al_pulse7_midpoint_time_quarter')
    assert fine and coarse and fine['complete'] and coarse['complete']
    assert fine['through_s']==127 and coarse['through_s']==127
    comparison=configuration_comparison(coarse['configuration'],fine['configuration'])
    assert comparison['physical_model_identical']
    differences={k:fine['sampled_maxima'][k]['temperature_C']-coarse['sampled_maxima'][k]['temperature_C'] for k in fine['sampled_maxima']}
    return dict(runtime=CONTROL,accepted_record_sha256=sha(accepted_path),
                independent_comparison_sha256=sha(comparison_path),native_audit=checked,
                coarse=coarse,fine=fine,configuration_comparison=comparison,
                casing_peak_differences_K=differences,
                remaining_difference_mm=fine['remaining_mm']-coarse['remaining_mm'],
                qualification='Full native verification permits continuation of refinement. This mixed geometry/mesh/control comparison is not an isolated radial-mesh convergence claim.')


def verify_manifest(runtime):
    for name,want in read(runtime/'input_manifest.json').items():
        assert sha(runtime/name)==want,(runtime.name,name)


def prepare():
    disks()
    review=terminal_control()  # Must occur before any configuration or runtime write.
    mapping=inventory()
    if RECORD.exists():
        prior=read(RECORD)
        assert prior['mapping']==mapping and prior['status']=='PREPARED_NOT_ACTIVATED'
    records=[]
    for parent_name,name in mapping.items():
        disks();parent=TMP/'runs'/parent_name;target=TMP/'runs'/name
        verify_manifest(parent)
        if name==CONTROL:
            records.append(dict(parent=parent_name,runtime=name,reused_verified_control=True,
                                config_sha256=sha(target/'config.json'),geometry=geometry_audit(target)))
            continue
        cfg=proposed(parent_name,name);path=ROOT/'configs'/f'{name}.json'
        if target.exists() or path.exists():
            # A prior preparation can be reused only if complete, exact and never run.
            assert path.exists() and target.exists() and read(path)==cfg and read(target/'config.json')==cfg
            assert not (target/'state.json').exists() and not list(target.glob('host_launch*'))
            verify_manifest(target)
        else:
            atomic(path,cfg)
            subprocess.run([sys.executable,str(ROOT/'model/prepare_model.py'),'--config',str(path),'--output',str(target)],check=True,stdout=subprocess.DEVNULL)
        unchanged={}
        for filename in ['material_v0.apdl','export_fields.mac','coupler.py','usermatth.F','usermatthLib.dll']:
            assert sha(parent/filename)==sha(target/filename),filename
            unchanged[filename]=sha(target/filename)
        old=read(parent/'config.json')
        for filename in ['run_v0.inp','resume_v0.inp']:
            expected=(parent/filename).read_text().replace(parent_name,name).replace(
                f"CNVTOL,HEAT,,{old['numerics']['native_heat_flow_tolerance']:.12g},2,1e-6",
                'CNVTOL,HEAT,,1e-07,2,1e-6')
            assert expected==(target/filename).read_text(),filename
        change=configuration_comparison(
            configuration_descriptor(old,read(parent/'input_manifest.json')),
            configuration_descriptor(cfg,read(target/'input_manifest.json')))
        assert change['physical_model_identical']
        assert set(change['numerical_changes'])<={'angle_deg','mesh_measure_convention','native_heat_flow_tolerance'}
        records.append(dict(parent=parent_name,runtime=name,reused_verified_control=False,
                            config_sha256=sha(target/'config.json'),input_manifest_sha256=sha(target/'input_manifest.json'),
                            unchanged_inputs=unchanged,configuration_comparison=change,geometry=geometry_audit(target)))
        print('Prepared without launch:',name,flush=True)
    sources=['configs/campaign_queue.json','validation/native_resolution_plan.json',
             'validation/native_sensitivity_plan.json','validation/native_cutoff_plan.json']
    atomic(RECORD,dict(prepared_utc=utc(),status='PREPARED_NOT_ACTIVATED',mapping=mapping,
                       control_review=review,records=records,
                       prior_mapping_sha256={p:sha(ROOT/p) for p in sources},
                       qualification='Fresh inputs only. No solver launch, no inherited state and no old package mutation. Eight further resolution cases and five deferred controls; the accepted sustainer Al control supplies the first 160-row record.'))


def activate():
    disks();record=read(RECORD)
    assert record['status']=='PREPARED_NOT_ACTIVATED'
    terminal_control()
    # Activation itself does not dispatch. Still require the old observer and solver to be gone.
    campaign=read(ROOT/'configs/campaign_queue.json')
    pid=campaign.get('current_observer_pid')
    if pid:
        p=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
        assert 'run_queue.py' not in p.stdout, 'Existing queue observer is still active'
    count=int(guest("@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^(ANSYS(?:\\d+)?|mpiexec|hydra_pmi_proxy)[.]exe$'}).Count").strip())
    assert count==0,'Another native solve is active'
    for path,want in record['prior_mapping_sha256'].items():assert sha(ROOT/path)==want,path
    mapping=record['mapping']
    for item in record['records']:
        runtime=TMP/'runs'/item['runtime'];verify_manifest(runtime)
        assert sha(runtime/'config.json')==item['config_sha256']
        if item['runtime']!=CONTROL:
            assert not (runtime/'state.json').exists() and not list(runtime.glob('host_launch*'))
    for relative in ['validation/native_resolution_plan.json','validation/native_sensitivity_plan.json']:
        p=ROOT/relative;plan=read(p)
        for entry in plan['cases']:
            old=entry['runtime']
            if old not in mapping:continue
            entry['prior_geometry_runtime']=old;entry['prior_geometry_config_sha256']=entry['config_sha256']
            entry['runtime']=mapping[old];entry['config_sha256']=sha(TMP/'runs'/mapping[old]/'config.json')
            entry['geometry_measures']='straight_sided_hex';entry['sector_angle_deg']=.05
            entry['native_heat_flow_tolerance']=1e-7
            entry['initial_status']='VERIFIED_COMPLETED_CONTROL' if mapping[old]==CONTROL else 'PREPARED_NOT_DISPATCHED'
        plan['geometry_update']='Fresh geometry-consistent successors; historical packages preserved. Mixed comparisons are explicitly labelled.'
        atomic(p,plan)
    p=ROOT/'validation/native_cutoff_plan.json';plan=read(p);old=plan['runtime']
    plan.update(prior_geometry_runtime=old,prior_geometry_config_sha256=plan['configuration_sha256'],
                runtime=mapping[old],configuration_sha256=sha(TMP/'runs'/mapping[old]/'config.json'),
                geometry_update='Fresh 0.05-degree exact-measure successor at 1e-7 heat-flow tolerance. Its own cylindrical reference verifies implementation. Comparison with the older default native case also changes geometry/tolerance and cannot isolate cutoff effects alone.')
    atomic(p,plan)
    campaign['superseded_dispatch_geometry_legacy']=campaign['current_dispatch']
    campaign['historical_geometry_dispatch_hold']=campaign.pop('dispatch_hold')
    campaign['geometry_successors']=mapping
    campaign['current_dispatch']=[mapping[n] for n in campaign['current_dispatch'] if n in mapping and mapping[n]!=CONTROL]
    assert len(campaign['current_dispatch'])==8
    for key in ['prepared_resolution_runtimes','deferred_sensitivity_runtimes','deferred_cutoff_runtimes']:
        campaign[key]=[mapping.get(n,n) for n in campaign[key]]
    campaign.update(current_observer_pid=None,diagnostic_dispatch=[],
                    current_observer_role='geometry_successors_prepared_not_dispatched',
                    geometry_activation_utc=utc(),
                    notes='Geometry control completed and verified. Eight geometry-consistent resolution successors ready for one serial ten-core queue; five controls remain deferred. Original one-core and 0.5-degree inputs are preserved.')
    atomic(ROOT/'configs/campaign_queue.json',campaign)
    record.update(status='ACTIVATED_NOT_DISPATCHED',activated_utc=utc())
    atomic(RECORD,record)
    print(json.dumps(campaign['current_dispatch'],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['plan','review','prepare','activate']);args=parser.parse_args()
    if args.action=='plan':print(json.dumps(inventory(),indent=2))
    elif args.action=='review':
        disks();review=terminal_control()
        review.update(reviewed_utc=utc(),status='NATIVE_CONTROL_TERMINAL_VERIFIED')
        atomic(ROOT/'validation/native_geometry_control_terminal.json',review)
        print(json.dumps({k:review[k] for k in ['runtime','status','casing_peak_differences_K','remaining_difference_mm','qualification']},indent=2))
    elif args.action=='prepare':prepare()
    else:activate()

"""Recheck the CF320 terminal record before handing the VM to continuous heating."""
import json
from pathlib import Path
import re

from continuous_heating_campaign import digest
from ops import ROOT, TMP, StorageLimitError, atomic, disks, host_check, stop_runs, utc
from run_native_wall_verification import CF
from validate_run import validate


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def warning_type(block):
    if 'Ansys, Inc.-supplied version of coding for USERCK has been used.' in block:
        return 'USERCK startup notice'
    match = re.search(r'Material property KXX of material 2 .*?temperature of\s+([\d.]+), .*?below the supplied temperature',block,re.S)
    if match and 0 < 22.-float(match[1]) < 1.e-5:
        return 'CF conductivity table endpoint within 0.00001 K of 22 C'
    if 'elapsed time exceeds the CPU time' in block:
        return 'Wall-clock performance advisory'
    if 'a solution was performed using 10 CPU cores' in block and 'distributed-memory parallel' in block:
        return 'SMP performance advisory'
    raise ValueError('Inspect unclassified native warning: '+block[:500])


def evaluate(runtime):
    name = runtime.name
    val = ROOT/'validation'
    paths = {key:val/f'{key}_{name}.json' for key in
             ('accepted','queue','native_pulse_comparison','native_uniformity')}
    accepted, queue, comp, uniform = (read(p) for p in paths.values())
    assert len(queue)==1 and queue[0]['runtime']==accepted['runtime']==comp['runtime']==name
    assert validate(runtime)==accepted and accepted['passed'] and accepted['native_logs']
    state = read(runtime/'state.json')
    cfg = read(runtime/'config.json')
    assert accepted['status']==queue[0]['status']==state['status']=='CASE_PROPERTY_LIMIT_REACHED'
    assert queue[0]['accepted_index']==accepted['accepted_steps']==comp['accepted_native_index']==state['index']
    assert queue[0]['time_s']==accepted['time_s']==comp['accepted_native_time_s']==state['time_s']
    assert comp['comparison_passed'] and comp['native_control_checks_passed']
    assert comp['persistent_native_topology_passed'] and comp['cooling_transition_passed']
    assert all(e['load_transfer_passed'] for e in comp['removal_events'])
    assert len(uniform['records'])==1
    u=uniform['records'][0]
    assert u['runtime']==name and u['through_s']==state['time_s'] and u['accepted_record_sha256']==digest(paths['accepted'])
    cp = runtime/'checkpoints'
    for sample in comp['comparisons']:
        assert sample['native_state_sha256']==digest(cp/f"state_{sample['index']:06d}.json.gz")
    manifest = runtime/f"accepted_restart_{state['index']%2}"/'manifest.json'
    restart = read(manifest)
    assert restart['accepted_index']==state['index'] and restart['accepted_time_s']==state['time_s']
    assert restart['files'] and any(k.endswith('.rdb') for k in restart['files'])
    assert any(re.search(r'\.r\d+$',k) for k in restart['files'])
    for phase in ('preflight','run'):
        assert read(runtime/f'phase_{phase}_exit.json')['ok']
        intent=read(runtime/f'host_launch_intent_{phase}.json')
        receipt=read(runtime/f'guest_launch_receipt_{phase}.json')
        host=read(runtime/f'host_launch_{phase}.json')
        assert intent['nonce']==receipt['nonce'] and receipt['ReturnValue']==0 and receipt['ProcessId']>0
        assert json.loads(host['guest'])==receipt
    logs=[]
    for item in accepted['native_logs']:
        log=(runtime/item['name']).read_text(errors='replace')
        count=re.search(r'NUMBER OF WARNING MESSAGES ENCOUNTERED=\s*(\d+)',log)
        assert count and int(count[1])==log[:count.start()].count('*** WARNING ***')
        assert '*** ERROR ***' not in log and re.findall(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)',log)==['0']
        assert re.search(r'Total number of cores requested\s*:\s*10\s*\(Shared Memory Parallel\)',log)
        assert re.search(r'Number of processes requested\s*:\s*1\b',log)
        assert re.search(r'Number of threads per process requested\s*:\s*10\b',log)
        logs.append(dict(**item,warnings_before_footer=int(count[1]),
                         warnings_after_footer=log[count.end():].count('*** WARNING ***')))
    classes=[warning_type(block) for block in accepted['warning_blocks']]
    limit=cfg['case_property_limit_C']
    previous=0.
    for i in range(1,state['index']+1):
        if i%250==1: host_check()
        a=read(cp/f'audit_{i:06d}.json')
        assert a['case_property_range_exceeded']==(i==state['index'])==(a['case_inner_max_C']>limit)
        if i<state['index']: previous=a['time_s']
    return dict(passed=True,runtime=name,steps=state['index'],property_limit_C=limit,
                first_crossing_bracket_s=[previous,state['time_s']],inner_casing_max_C=a['case_inner_max_C'],
                remaining_liner_mm=1000*a['phenolic_remaining_thickness_m'],
                full_field_ranges=u['maximum_same_radius_ranges'],max_profile_difference_K=max(
                    x['max_live_profile_difference_K'] for x in comp['comparisons']),row_load_transfers=len(comp['removal_events']),
                restart_manifest_sha256=digest(manifest),restart_files_verified=len(restart['files']),
                receipts_sha256={k:digest(p) for k,p in paths.items()},log_checks=logs,warning_classes=classes,
                auditor_sha256=digest(Path(__file__)),qualification='Native pulse-cooling control. Separate from the continuous liner event.')


if __name__=='__main__':
    try:
        disks()
        result=evaluate(TMP/'runs'/CF)
        atomic(ROOT/'validation/native_cf320_handoff.json',dict(checked_utc=utc(),**result))
        print(json.dumps(result,indent=2))
    except StorageLimitError as exc:
        stop_runs(str(exc))
        raise

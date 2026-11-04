"""Serial native-job queue; never retries an unexplained failed simulation."""
import argparse
import json
import subprocess
import sys
import time
from ops import ROOT, TMP, atomic, disks, utc
from validate_run import validate

def phase(runtime, action, wait_existing=False):
    done=runtime/('phase_'+action+'_exit.json')
    launched=(runtime/('host_launch_'+action+'.json')).exists()
    if not done.exists() and not wait_existing and not launched:
        disks()
        subprocess.run([sys.executable,str(ROOT/'model/launch_case.py'),runtime.name,action],check=True)
    while not done.exists():
        disks()
        if (runtime/'coupler_error.txt').exists():
            raise RuntimeError((runtime/'coupler_error.txt').read_text())
        time.sleep(10)
    status=json.loads(done.read_text(encoding='utf-8-sig'))
    if not status.get('ok'):
        raise RuntimeError(f'{runtime.name}/{action}: {status}')

def main():
    p=argparse.ArgumentParser();p.add_argument('runtimes',nargs='+')
    p.add_argument('--wait-resume-first',action='store_true',help='Observe an explicitly launched first resume without launching another')
    args=p.parse_args()
    records=[]
    for index,name in enumerate(args.runtimes):
        runtime=TMP/'runs'/name
        print(f'{utc()} checking {name}',flush=True)
        if name=='booster_al_baseline7_n20_dt0125' and not (ROOT/'validation/topology_benchmark.json').exists():
            # Controlled native verification between jobs, never alongside a
            # live simulation. This fixture has analytical reference values.
            subprocess.run([sys.executable,str(ROOT/'model/topology_benchmark.py')],check=True)
        if name=='booster_cf_baseline7_n20_dt0125' and not (ROOT/'validation/reaction_benchmark.json').exists():
            subprocess.run([sys.executable,str(ROOT/'model/reaction_benchmark.py')],check=True)
        phase(runtime,'preflight')
        if index==0 and args.wait_resume_first:
            phase(runtime,'resume',wait_existing=True)
        else:
            phase(runtime,'run')
        cfg=json.loads((runtime/'config.json').read_text())
        state=json.loads((runtime/'state.json').read_text())
        if state['status'] not in ['COMPLETED_HORIZON','PHENOLIC_CONSUMED','CASE_PROPERTY_LIMIT_REACHED']:
            raise RuntimeError(f'{name}: unexpected terminal state {state["status"]}')
        if state['status']=='COMPLETED_HORIZON':
            assert abs(state['time_s']-cfg['end_time_s'])<1e-8
        audit_path=runtime/'checkpoints'/f'audit_{state["index"]:06d}.json'
        audit=json.loads(audit_path.read_text())
        assert audit['energy_relative_error']<=cfg['numerics']['energy_relative_tolerance']
        assert audit['hot_power_relative_error']<=cfg['numerics']['hot_power_relative_tolerance']
        verified=validate(runtime)
        atomic(ROOT/'validation'/('accepted_'+name+'.json'),verified)
        record=dict(runtime=name,accepted_index=state['index'],time_s=state['time_s'],status=state['status'],last_audit=audit)
        records.append(record)
        atomic(ROOT/'validation'/('queue_'+args.runtimes[0]+'.json'),records)
        atomic(TMP/'active_runs.json',[])
        print(f'{utc()} accepted {name} at {state["time_s"]} s',flush=True)

if __name__=='__main__':
    main()

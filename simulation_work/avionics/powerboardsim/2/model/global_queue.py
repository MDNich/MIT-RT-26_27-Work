"""Supervise one native MAPDL job at a time, preserving uncertain or failed launches for inspection."""
import datetime,fcntl,hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RT=ROOT/'.runtime'
CAMPAIGN='nov08_01'
RECEIPTS=RT/'receipts'/CAMPAIGN
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,value):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.new');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(p)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def log(s):print(utc(),s,flush=True)
def launch(script,flags,dest):
    if dest.exists():return
    save(dest,dict(request_utc=utc(),script=script,arguments=flags))
    folder = r"\\Mac\Home\Developer\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\2\model"
    path = folder + chr(92) + script
    assert all(re.fullmatch(r'[-A-Za-z0-9_]+',s) for s in flags)
    cmd='powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File '+path+' '+' '.join(flags)
    ps="Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='"+cmd+"'}|Select-Object ProcessId,ReturnValue|ConvertTo-Json"
    run=subprocess.run([sys.executable,str(ROOT/'model/guest_command.py')],input=ps,text=True,capture_output=True)
    if run.returncode:raise RuntimeError('Guest launch outcome uncertain; inspect the case directory.')
    out=json.loads(run.stdout.lstrip('\ufeff'))
    if out['ReturnValue']!=0:raise RuntimeError(str(out))
    save(dest,dict(request_utc=utc(),script=script,arguments=flags,**out))
def jobs():
    yield 'bare_static',''
    yield 'bare_original',''
    yield 'bare_refined',''
    for source in ('bare_original','bare_refined'):
        name=source+'_sturm'
        if (ROOT/f'validation/{name}_input.json').is_file():yield name,''
    # Run a paired edge-cell fixture early while the full global series is still pending.
    yield 'bare_lateral_friction_locked',''
    yield 'stand3_nylon_lateral_friction_locked','bare_lateral_friction_locked'
    yield 'stand3_nylon_static',''
    # Establish the first complete reference and one cased comparison before the remaining variants.
    for branch in ['bare','stand3_nylon','flush_nylon','stand3_aluminium','flush_aluminium']:
        if branch not in ('bare','stand3_nylon'):
            yield branch+'_static',''
        yield branch+'_basis',branch+'_static'
        yield branch+'_modal20',branch+'_static'
        for axis in 'XYZ':yield branch+'_psd_'+axis,branch+'_basis'
        if branch!='bare':
            for case in ('original','refined'):yield branch+'_'+case,''
    local_cases=read(ROOT/'validation/local_jobs.json')
    for case,meta in local_cases.items():
        if case in ('bare_lateral_friction_locked','stand3_nylon_lateral_friction_locked'):continue
        yield case,'' if case.startswith('bare_') else 'bare_'+meta['source']

def result_path(case):
    local='_lateral_' in case or '_damage_' in case
    return ROOT/'validation'/('local' if local else 'global')/(case+'.json')

def run():
    for case,parent in jobs():
        receipt=RECEIPTS/case;receipt.mkdir(parents=True,exist_ok=True)
        final=result_path(case)
        partial=ROOT/'validation/partial_local'/(case+'.json')
        if final.exists() or partial.exists():continue
        if parent and not result_path(parent).is_file() and not (ROOT/'validation/partial_local'/(parent+'.json')).is_file():
            log('Parent unaccepted: '+case);continue
        if not case.startswith('bare_') and not (ROOT/'validation/cased_preflight.json').is_file():
            raise RuntimeError('Cased preflight review pending')
        local=final.parent.name=='local'
        if local and not case.startswith('bare_') and not (ROOT/'validation/local_cased_preflight.json').is_file():
            raise RuntimeError('Cased pull fixture preflight review pending')
        if (receipt/'audit_failed.txt').exists():continue
        if shutil.disk_usage(ROOT).free<400_000_000_000:raise RuntimeError('Host storage reserve reached')
        state=receipt/'status.json'
        if not state.exists():
            flags=['-Case',case,'-Campaign',CAMPAIGN]
            if parent and not local:flags.extend(['-Parent',parent])
            log('Dispatch '+case);launch('native_run.ps1',flags,receipt/'dispatch.json')
        while not state.is_file():time.sleep(15)
        while read(state)['phase'] not in ('solver_complete','failed'):time.sleep(20)
        if read(state)['phase']=='failed':log('Failed native '+case);continue
        if not (receipt/'released.txt').exists():
            log('Archive '+case);launch('archive_native.ps1',['-Case',case,'-Campaign',CAMPAIGN],receipt/'archive_request.json')
        while not (receipt/'released.txt').exists():time.sleep(20)
        audit='audit_local.py' if local else 'audit_global.py'
        r=subprocess.run([sys.executable,str(ROOT/'model'/audit),case,CAMPAIGN],text=True,capture_output=True)
        log(r.stdout[-1000:])
        if r.returncode:(receipt/'audit_failed.txt').write_text(r.stderr);log('Audit failed '+case+': '+r.stderr[-330:])
    log('All available global tasks visited. Check receipts, deferred parents and material scope.')
if __name__=='__main__':
    lock=(RT/'global_queue.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    save(RT/'global_queue.json',dict(pid=os.getpid(),started=utc(),campaign=CAMPAIGN))
    run()

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
    yield 'stand3_nylon_lateral_friction_locked_pin1','bare_lateral_friction_locked'
    yield 'stand3_nylon_static',''
    # Compare the first two prestressed modal bases before assigning the longer histories.
    yield 'bare_basis','bare_static'
    yield 'stand3_nylon_basis','stand3_nylon_static'
    # Establish the first complete reference and one cased comparison before the remaining variants.
    for branch in ['bare','stand3_nylon','flush_nylon','stand3_aluminium','flush_aluminium']:
        if branch.startswith('flush_'):
            # These original decks start overclosed. A separately named successor with a
            # verified installed restart must be mapped explicitly, never enabled by a flag.
            log('Holding original overclosed global branch: '+branch);continue
        if branch not in ('bare','stand3_nylon'):
            yield branch+'_static',''
        if branch not in ('bare','stand3_nylon'):yield branch+'_basis',branch+'_static'
        if branch in ('bare','stand3_nylon') and (ROOT/'validation/local_install_jobs.json').is_file():
            metal='nylon' if branch=='bare' else 'aluminium'
            name='flush_'+metal+'_lateral_friction_locked_approach1'
            if name in read(ROOT/'validation/local_install_jobs.json'):
                yield name,'bare_lateral_friction_locked'
        yield branch+'_modal20',branch+'_static'
        for axis in 'XYZ':
            yield branch+'_psd_'+axis,branch+'_basis'
            if branch=='bare' and axis=='X':
                # Establish the first like-for-like native PSD before the broader history series.
                yield 'stand3_nylon_psd_X','stand3_nylon_basis'
                yield 'stand3_aluminium_static',''
                yield 'stand3_aluminium_basis','stand3_aluminium_static'
                if (ROOT/'validation/board_surface_jobs.json').exists():
                    yield 'flush_nylon_surf1_static',''
            if branch=='bare' and axis=='Z' and (ROOT/'validation/board_surface_jobs.json').exists():
                yield 'flush_aluminium_surf1_static',''
        yield branch+'_enforced',branch+'_basis'
        for axis in 'XYZ':yield branch+'_motion_'+axis,branch+'_enforced'
        if branch!='bare':
            for case in ('original','refined'):yield branch+'_'+case,''
    local_cases=read(ROOT/'validation/local_jobs.json')
    # The original local contact search failed the CAD check. Release only separately
    # sealed raised successors; flush still needs a verified nickel contact surface.
    for case in local_cases:
        if case.startswith('bare_') and case!='bare_lateral_friction_locked':yield case,''
    for case,meta in read(ROOT/'validation/local_contact_retries.json').items():
        if case!='stand3_nylon_lateral_friction_locked_pin1':
            yield case,'bare_'+meta['source']

def result_path(case):
    local='_lateral_' in case or '_damage_' in case
    category = 'motion' if case.endswith('_enforced') or '_motion_' in case else ('local' if local else 'global')
    return ROOT/'validation'/category/(case+'.json')

def run():
    for case,parent in jobs():
        # A sealed geometry-only check runs between jobs; its results cannot
        # release a flush load case without a separate installed-state audit.
        if case=='stand3_nylon_static':
            probe=RT/'flush_approach_v1'
            if (probe/'pre.inp').exists() and not (probe/'exit.txt').exists():
                if shutil.disk_usage(ROOT).free<400_000_000_000:raise RuntimeError('Host storage reserve reached')
                launch('flush_install_check.ps1',['-Trial',probe.name],probe/'dispatch.json')
                while not (probe/'exit.txt').is_file():
                    if (probe/'failed.txt').exists():raise RuntimeError('Unexpected preflight state; inspect guest before dispatch')
                    time.sleep(10)
        controls=[]
        if case=='bare_basis':
            controls=[('board_actuator_control_v1','control.inp','board_actuator_control','actuator_control.ps1','actuator_control.py'),
                      ('board_initial_v1','pre.inp','board_initial_approach','flush_install_check.ps1','board_initial_check.py')]
        # When reattaching, never insert a new control in front of an already dispatched case.
        if case in ('flush_nylon_lateral_friction_locked_approach1','bare_modal20','bare_psd_X','bare_psd_Y','bare_psd_Z') and not (RECEIPTS/case/'dispatch.json').exists():
            controls=[('seat_surface_control_v1','control.inp','seat_surface_control','actuator_control.ps1','seat_surface_control.py'),
                      ('board_surface_initial_v1','pre.inp','board_surface_initial','flush_install_check.ps1','surface_board.py')]
        if controls:
            # These short checks are serial native jobs; a known numerical rejection only
            # holds the installation branch. An ambiguous live job blocks further dispatch.
            for name,inp,publication,runner,auditor in controls:
                probe=RT/name
                if not (probe/inp).is_file() or (ROOT/f'validation/{publication}.json').exists():continue
                if shutil.disk_usage(ROOT).free<400_000_000_000:raise RuntimeError('Host storage reserve reached')
                if not (probe/'exit.txt').exists() and not (probe/'failed.txt').exists():
                    launch(runner,['-Trial',name],probe/'dispatch.json')
                    while not (probe/'exit.txt').exists():
                        if (probe/'failed.txt').exists():raise RuntimeError('Uncertain native control: '+name)
                        time.sleep(5)
                if (probe/'failed.txt').exists():raise RuntimeError('Uncertain native control: '+name)
                if not (probe/'audit_failed.txt').exists():
                    r=subprocess.run([sys.executable,str(ROOT/'model'/auditor),'audit'],capture_output=True,text=True)
                    if r.returncode:(probe/'audit_failed.txt').write_text(r.stderr);log('Rejected '+name+'; bare jobs independent')
        receipt=RECEIPTS/case;receipt.mkdir(parents=True,exist_ok=True)
        final=result_path(case)
        partial=ROOT/'validation/partial_local'/(case+'.json')
        review=ROOT/'validation/review_local'/(case+'.json')
        if final.exists() or partial.exists() or review.exists() or (ROOT/'validation/review_global'/(case+'.json')).exists():continue
        if parent and not result_path(parent).is_file() and not (ROOT/'validation/partial_local'/(parent+'.json')).is_file():
            log('Parent unaccepted: '+case);continue
        if not case.startswith('bare_') and not (ROOT/'validation/cased_preflight.json').is_file():
            raise RuntimeError('Cased preflight review pending')
        local=final.parent.name=='local'
        motion=final.parent.name=='motion'
        if local and not case.startswith('bare_') and not (ROOT/'validation/local_cased_preflight.json').is_file():
            raise RuntimeError('Cased pull fixture preflight review pending')
        if (receipt/'audit_failed.txt').exists():continue
        if shutil.disk_usage(ROOT).free<400_000_000_000:raise RuntimeError('Host storage reserve reached')
        state=receipt/'status.json'
        if not state.exists():
            if '_psd_' in case and not case.startswith('bare_') and not (receipt/'dispatch.json').exists():
                from stage_remote_psd import stage as stage_psd
                stage_psd(case.rsplit('_psd_',1)[0],CAMPAIGN)
            if motion:
                from stage_motion import stage
                branch=case.removesuffix('_enforced').split('_motion_')[0]
                stage(branch,CAMPAIGN)
            flags=['-Case',case,'-Campaign',CAMPAIGN]
            if parent and not local:flags.extend(['-Parent',parent])
            log('Dispatch '+case);launch('native_run.ps1',flags,receipt/'dispatch.json')
        while not state.is_file():time.sleep(15)
        while read(state)['phase'] not in ('solver_complete','failed'):time.sleep(20)
        if read(state)['phase']=='failed':log('Failed native '+case);continue
        if not (receipt/'released.txt').exists():
            log('Archive '+case);launch('archive_native.ps1',['-Case',case,'-Campaign',CAMPAIGN],receipt/'archive_request.json')
        while not (receipt/'released.txt').exists():time.sleep(20)
        audit='audit_board_surface.py' if case.endswith('_surf1_static') else ('audit_install.py' if case.endswith('_approach1') else ('audit_local.py' if local else 'audit_global.py'))
        args=['audit_motion.py','case',case,CAMPAIGN] if motion else [audit,case,CAMPAIGN]
        r=subprocess.run([sys.executable,str(ROOT/'model'/args[0]),*args[1:]],text=True,capture_output=True)
        log(r.stdout[-1000:])
        if r.returncode:(receipt/'audit_failed.txt').write_text(r.stderr);log('Audit failed '+case+': '+r.stderr[-330:])
    log('All available global tasks visited. Check receipts, deferred parents and material scope.')
if __name__=='__main__':
    lock=(RT/'global_queue.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    save(RT/'global_queue.json',dict(pid=os.getpid(),started=utc(),campaign=CAMPAIGN))
    run()

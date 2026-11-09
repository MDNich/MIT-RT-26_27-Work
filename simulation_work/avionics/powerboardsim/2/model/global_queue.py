"""Supervise one native MAPDL job at a time, preserving uncertain or failed launches for inspection."""
import datetime,fcntl,hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
from study_cases import native_case
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
def archive_closed_case(case,receipt):
    """Reconcile a dropped archive acknowledgement without repeating a structural solve."""
    if (receipt/'released.txt').is_file():
        return
    if read(receipt/'status.json')['phase']!='solver_complete':
        raise RuntimeError('Native completion required before archive')
    for attempt in range(3):
        path=receipt/('archive_request.json' if attempt==0 else f'archive_retry_{attempt}.json')
        if not path.exists():
            try:
                launch('archive_native.ps1',['-Case',case,'-Campaign',CAMPAIGN],path)
            except (ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                log(f'Archive acknowledgement uncertain for {case}: {exc}')
        absent=0
        while absent<2:
            if (receipt/'released.txt').is_file():
                return
            if (receipt/'archive_error.txt').exists():
                raise RuntimeError((receipt/'archive_error.txt').read_text(errors='replace')[:350])
            time.sleep(8)
            if (receipt/'released.txt').is_file():
                return
            # Only an explicit, successful guest process inquiry can establish absence.
            ps=("$p=Get-CimInstance Win32_Process -ErrorAction Stop; "
                "$a=@($p|Where-Object { $_.Name -eq 'powershell.exe' -and "
                f"$_.CommandLine -like '*\\archive_native.ps1 -Case {case} -Campaign {CAMPAIGN}*' }}); "
                "$s=@($p|Where-Object { $_.Name -match '^ANSYS(261)?\\.exe$' }); "
                "@{archiver=$a.Count;solver=$s.Count}|ConvertTo-Json -Compress")
            check=subprocess.run([sys.executable,str(ROOT/'model/guest_command.py'),'--timeout','20'],
                                 input=ps,text=True,capture_output=True)
            try:
                guest=json.loads(check.stdout.lstrip('\ufeff')) if check.returncode==0 else None
            except ValueError:
                guest=None
            absent=absent+1 if guest=={'archiver':0,'solver':0} else 0
        log('No guest archiver or solver in two consecutive checks for '+case)
    raise RuntimeError('Closed native result needs archive inspection: '+case)

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
            # Only the installed, opposed-face static branch supplies the prestressed descendants.
            state=native_case(branch,'static')
            basis=native_case(branch,'basis')
            yield basis,state
            yield native_case(branch,'modal20'),state
            for axis in 'XYZ':yield native_case(branch,'psd_'+axis),basis
            enforced=native_case(branch,'enforced');yield enforced,basis
            for axis in 'XYZ':yield native_case(branch,'motion_'+axis),enforced
            continue
        if branch not in ('bare','stand3_nylon'):
            yield branch+'_static',''
        if branch not in ('bare','stand3_nylon'):yield branch+'_basis',branch+'_static'
        if branch in ('bare','stand3_nylon') and (ROOT/'validation/local_install_jobs.json').is_file():
            metal='nylon' if branch=='bare' else 'aluminium'
            name='flush_'+metal+'_lateral_friction_locked_approach1'
            if metal=='nylon' and name in read(ROOT/'validation/local_install_jobs.json'):
                yield name,'bare_lateral_friction_locked'
            if metal=='aluminium' and (ROOT/'validation/local_seat_jobs.json').is_file():
                yield name.replace('_approach1','_seatfaces1'),'bare_lateral_friction_locked'
        if branch=='bare' and (ROOT/'validation/contact_patch_inputs.json').is_file():
            # The matching free submodel checks the cut-boundary motion before imposing contact.
            yield 'patch_stand3_nylon_span9_free_v1','stand3_nylon_basis'
            yield 'patch_stand3_nylon_span9_contact_v1','patch_stand3_nylon_span9_free_v1'
        yield branch+'_modal20',branch+'_static'
        if branch=='bare' and (ROOT/'validation/contact_patch_inputs.json').is_file():
            yield 'patch_stand3_nylon_span9_contact_eq1','patch_stand3_nylon_span9_free_v1'
            yield 'patch_stand3_nylon_span15_free_v1','stand3_nylon_basis'
            yield 'patch_stand3_nylon_span15_contact_eq1','patch_stand3_nylon_span15_free_v1'
        for axis in 'XYZ':
            yield native_case(branch,'psd_'+axis),branch+'_basis'
            if branch=='bare' and axis=='X':
                # Establish the first like-for-like native PSD before the broader history series.
                yield 'stand3_aluminium_static',''
                yield native_case('stand3_nylon','psd_X'),'stand3_nylon_basis'
                yield 'bare_psd_Y','bare_basis'
                yield 'bare_psd_Z','bare_basis'
                yield 'stand3_aluminium_basis','stand3_aluminium_static'
                yield native_case('stand3_aluminium','psd_X'),'stand3_aluminium_basis'
                if (ROOT/'validation/board_surface_jobs.json').exists():
                    yield 'flush_nylon_surf1_static',''
                if (ROOT/'validation/local_seat_jobs.json').is_file():
                    yield 'flush_nylon_lateral_friction_locked_seatfaces1','bare_lateral_friction_locked'
            if branch=='bare' and axis=='Z' and (ROOT/'validation/board_surface_jobs.json').exists():
                yield 'flush_aluminium_surf1_static',''
        if (ROOT/'validation/contact_replay_inputs.json').is_file() and branch in ('bare','stand3_nylon'):
            if branch=='bare':
                yield 'replay_stand3_nylon_span9_free_s4_v1','patch_stand3_nylon_span9_free_v1'
                yield 'replay_stand3_nylon_span9_contact_s4_v1','replay_stand3_nylon_span9_free_s4_v1'
            else:
                yield 'replay_stand3_nylon_span9_contact_s2_v1','replay_stand3_nylon_span9_contact_s4_v1'
                yield 'replay_stand3_nylon_span15_contact_s4_v1','patch_stand3_nylon_span15_contact_eq1'
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
    extra=ROOT/'validation/flush_pull_variants.json'
    if extra.exists():
        for case,record in read(extra).items():
            yield case,'bare_'+record['source']

def result_path(case):
    if case.startswith('replay_'):
        return ROOT/'validation/contact_replay'/(case+'.json')
    if case.startswith('patch_'):
        return ROOT/'validation/contact_patch'/(case+'.json')
    local='_lateral_' in case or '_damage_' in case
    category = 'motion' if case.endswith('_enforced') or '_motion_' in case else ('local' if local else 'global')
    return ROOT/'validation'/category/(case+'.json')

def ordered_jobs():
    sequence=list(jobs())
    parents=dict(sequence)
    pending=[]
    for folder in RECEIPTS.iterdir():
        state=folder/'status.json'
        if state.exists():
            phase=read(state)['phase']
            if phase=='failed' or (phase=='solver_complete' and (folder/'released.txt').exists()):
                continue
        elif not (folder/'dispatch.json').exists():
            continue
        pending.append(folder.name)
    if len(pending)>1 or any(name not in parents for name in pending):
        raise RuntimeError('Inspect existing guest jobs before dispatch: '+str(pending))
    if pending:
        case=pending[0]
        log('Reattaching current case '+case)
        yield case,parents[case]
    for case,parent in sequence:
        if case not in pending:
            yield case,parent

def run():
    supervisor=Path(__file__).resolve()
    initial_code=supervisor.read_bytes()
    for case,parent in ordered_jobs():
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
        if case in ('patch_stand3_nylon_span9_free_v1','bare_modal20') and not (RECEIPTS/case/'dispatch.json').exists():
            controls.append(('patch_table_control_v1','control.inp','patch_table_control','actuator_control.ps1','contact_transient.py'))
        if case in ('patch_stand3_nylon_span9_contact_eq1','bare_psd_X') and not (RECEIPTS/case/'dispatch.json').exists():
            controls.append(('local_seat_faces_v1','pre.inp','local_seat_preflight','flush_install_check.ps1','local_board_seats.py'))
        if case in ('bare_psd_Y','bare_psd_Z') and not (RECEIPTS/case/'dispatch.json').exists():
            mesh='refined' if case=='bare_psd_Y' else 'original'
            controls.append((f'default_{mesh}_initial_v1','pre.inp',f'default_{mesh}_initial','flush_install_check.ps1','default_install.py'))
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
                    args=[sys.executable,str(ROOT/'model'/auditor),'audit']
                    if auditor=='default_install.py':args.append(mesh)
                    r=subprocess.run(args,capture_output=True,text=True)
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
        if case.endswith('_minus_seatfaces1'):
            nominal=case.replace('_minus_seatfaces1','_seatfaces1')
            paths=[result_path(nominal),ROOT/'validation/review_local'/(nominal+'.json'),ROOT/'validation/partial_local'/(nominal+'.json')]
            if not any(p.is_file() and read(p).get('installed_state') is not None for p in paths):
                log('Reverse pull shares the nominal installation up to its first lateral increment: '+case)
                continue
        if case.startswith('replay_') and '_span9_contact_' in case and not result_path('patch_stand3_nylon_span9_contact_eq1').exists():
            log('Static contact check pending: '+case)
            continue
        if case.startswith('replay_') and not (ROOT/'validation/patch_table_control.json').is_file():
            log('Motion-table validation pending: '+case)
            continue
        local=final.parent.name=='local'
        motion=final.parent.name=='motion'
        if local and not case.startswith('bare_') and not (ROOT/'validation/local_cased_preflight.json').is_file():
            raise RuntimeError('Cased pull fixture preflight review pending')
        if (receipt/'audit_failed.txt').exists():continue
        if shutil.disk_usage(ROOT).free<400_000_000_000:raise RuntimeError('Host storage reserve reached')
        state=receipt/'status.json'
        if not state.exists():
            if '_psd_' in case and not case.startswith('bare_') and not (receipt/'dispatch.json').exists():
                from private_psd import stage as stage_psd
                branch,axis=case.removesuffix('_private1').rsplit('_psd_',1)
                stage_psd(branch,CAMPAIGN,axis)
            if motion:
                from stage_motion import stage
                branch=case.removesuffix('_enforced').split('_motion_')[0]
                stage(branch,CAMPAIGN)
            flags=['-Case',case,'-Campaign',CAMPAIGN]
            if case.startswith(('patch_','replay_')):
                flags.extend(['-Cores','2'])
            elif parent and not local:
                flags.extend(['-Parent',parent])
            log('Dispatch '+case);launch('native_run.ps1',flags,receipt/'dispatch.json')
        while not state.is_file():time.sleep(15)
        while read(state)['phase'] not in ('solver_complete','failed'):time.sleep(20)
        if read(state)['phase']=='failed':log('Failed native '+case);continue
        if not (receipt/'released.txt').exists():
            log('Archive '+case)
            archive_closed_case(case,receipt)
        audit='audit_board_surface.py' if case.endswith('_surf1_static') else ('audit_install.py' if case.endswith(('_approach1','_seatfaces1')) else ('audit_local.py' if local else 'audit_global.py'))
        if case.startswith('patch_'):
            audit='audit_contact_patch.py'
        elif case.startswith('replay_'):
            audit='audit_contact_replay.py'
        args=['audit_motion.py','case',case,CAMPAIGN] if motion else [audit,case,CAMPAIGN]
        r=subprocess.run([sys.executable,str(ROOT/'model'/args[0]),*args[1:]],text=True,capture_output=True)
        log(r.stdout[-1000:])
        if r.returncode:(receipt/'audit_failed.txt').write_text(r.stderr);log('Audit failed '+case+': '+r.stderr[-330:])
        if supervisor.read_bytes()!=initial_code:
            # Read revised scheduling only between audited jobs. The new process image first reconciles receipts.
            log('Loading updated schedule at a case boundary')
            os.execv(sys.executable,[sys.executable,'-u',str(supervisor)])
    log('All available global tasks visited. Check receipts, deferred parents and material scope.')
if __name__=='__main__':
    lock=(RT/'global_queue.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    save(RT/'global_queue.json',dict(pid=os.getpid(),started=utc(),campaign=CAMPAIGN))
    run()

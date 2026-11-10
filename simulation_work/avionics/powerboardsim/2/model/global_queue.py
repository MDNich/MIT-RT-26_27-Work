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
def wait_for_scratch(required):
    held=False
    while True:
        probe=subprocess.run([sys.executable,str(ROOT/'model/guest_command.py'),'--timeout','20'],
                             input='[string](Get-PSDrive C -ErrorAction Stop).Free',text=True,capture_output=True)
        value=probe.stdout.lstrip('\ufeff').strip()
        if probe.returncode==0 and value.isdecimal() and int(value)>=required:
            if held:log(f'Windows scratch ready: {value} bytes free')
            return
        if not held:log(f'Holding undispatched jobs pending {required} verified free bytes on C (readback {value[:100]!r})')
        held=True
        time.sleep(20)


def dispatch_solver(script,flags,folder):
    """Reconcile an uncertain Parallels acknowledgement with the guest before any later launch."""
    native=script=='native_run.ps1'
    name=folder.name
    expected=(folder/'status.json',) if native else (folder/'exit.txt',folder/'failed.txt')
    guest_dir='C:'+chr(92)+'Temp'+chr(92)+'PBCaseStudy'+chr(92)+(CAMPAIGN+chr(92) if native else '')+name
    arg='-Case' if native else '-Trial'
    if not re.fullmatch(r'[A-Za-z0-9_]+',name):raise ValueError(name)
    for attempt in range(3):
        request=folder/('dispatch.json' if attempt==0 else f'dispatch_retry_{attempt}.json')
        if any(p.exists() for p in expected):return
        if not request.exists():
            local=(RT/'inputs'/name/'local_job.json')
            required=24_000_000_000 if native and local.is_file() and read(local).get('load_protocol') in ('four_stage_install','grip_install') else 18_000_000_000
            wait_for_scratch(required)
            try:
                launch(script,flags,request)
            except (RuntimeError,ValueError,subprocess.TimeoutExpired) as exc:
                log(f'Uncertain {name} dispatch: {exc}')
        absent=0
        while absent<2:
            if any(p.exists() for p in expected):return
            time.sleep(8)
            if any(p.exists() for p in expected):return
            ps=("$all=@(Get-CimInstance Win32_Process -ErrorAction Stop);"
                "$launcher=@($all|Where-Object { $_.Name -eq 'powershell.exe' -and "
                f"$_.CommandLine -like '*{chr(92)}{script} {arg} {name}*' }});"
                "$sol=@($all|Where-Object { $_.Name -match '^(ANSYS(261)?|mapdl|mpiexec)\\.exe$' });"
                f"@{{runner=$launcher.Count;solver=$sol.Count;directory=(Test-Path -LiteralPath '{guest_dir}' -ErrorAction Stop)}}|ConvertTo-Json -Compress")
            check=subprocess.run([sys.executable,str(ROOT/'model/guest_command.py'),'--timeout','20'],
                                 input=ps,text=True,capture_output=True)
            try:
                guest=json.loads(check.stdout.lstrip('\ufeff')) if check.returncode==0 else None
            except ValueError:
                guest=None
            if guest=={'runner':0,'solver':0,'directory':True} and not any(p.exists() for p in expected):
                raise RuntimeError('Existing guest directory without a completion or live process: '+guest_dir)
            absent=absent+1 if guest=={'runner':0,'solver':0,'directory':False} else 0
        log('Confirmed unused guest directory and no runner or solver twice: '+name)
    raise RuntimeError('Guest dispatch could not be established: '+name)


def archive_closed_case(case,receipt):
    """Reconcile a dropped archive acknowledgement without repeating a structural solve."""
    if (receipt/'released.txt').is_file():
        return
    status=read(receipt/'status.json')
    if status['phase']!='solver_complete':
        raise RuntimeError('Native completion required before archive')
    if status.get('shared_scratch') and not (receipt/'archive_request.json').exists() and not (receipt/'archive.lock').exists():
        from archive_shared import archive
        archive(case,CAMPAIGN)
        return
    if case.startswith('snug125_') and status.get('motion_kind')=='transient' and not (receipt/'archive_request.json').exists():
        from motion_archive_clones import prefill
        try:
            prefill(case,CAMPAIGN,status,receipt)
        except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
            log(f'Modal clone prefill unavailable for {case}: {exc}; using native archive verification')
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

def capture_closed_installation(case, state, receipt):
    if state['phase']!='failed' or not case.endswith('_surf1_static') or not state.get('shared_scratch') or state.get('exit') is None:
        return
    work=RT/'shared_native'/CAMPAIGN/case
    if not (work/'file0.rst').is_file() or (work/'file.lock').exists():
        return
    saved=receipt/'terminal_partition_capture.json'
    if saved.is_file():
        return
    try:
        from partition_snapshot import capture
        snapshot=capture(case,CAMPAIGN,terminal=True)
        from film_identity import digest
        save(saved,dict(checkpoint=str(snapshot.relative_to(ROOT)),manifest_sha256=digest(snapshot/'receipts.json')))
    except (AssertionError,OSError,RuntimeError,ValueError) as exc:
        log(f'Partial result capture needs inspection for {case}: {type(exc).__name__} {exc}')


def recover_split_readbacks():
    from split_contact_post import location
    for case in ('flush_nylon_surf1_static','flush_aluminium_surf1_static'):
        folder=location(case,CAMPAIGN)
        receipt=RECEIPTS/case
        prior=receipt/'audit_failed.txt'
        if not prior.is_file() or not (folder/'request.json').is_file() or (folder/'audit_failed.txt').is_file():
            continue
        if not (folder/'exit.txt').is_file() and not (folder/'failed.txt').is_file():
            log('Dispatch postprocessing of all split contact faces for '+case)
            dispatch_solver('split_contact_post.ps1',['-Trial',folder.name],folder)
        if (folder/'failed.txt').is_file():
            log('Split-pair readback requires inspection: '+(folder/'failed.txt').read_text(errors='replace'))
            continue
        commands=[['split_contact_post.py','audit',case],['audit_board_surface.py',case,CAMPAIGN]]
        for args in commands:
            p=subprocess.run([sys.executable,str(ROOT/'model'/args[0]),*args[1:]],capture_output=True,text=True)
            if p.returncode:
                (folder/'audit_failed.txt').write_text(p.stdout+p.stderr)
                log('Readback audit rejected '+case+': '+p.stderr[-240:])
                break
        else:
            prior.rename(receipt/'original_incomplete_contact_selection.txt')
            log('Combined and partitioned installation readbacks reconciled: '+case)


def jobs():
    # Honour the new geometry at the next case boundary. Each listed input is independently sealed.
    snug = ROOT/'validation/snug125/global_inputs.json'
    if snug.is_file():
        inputs = read(snug)
        for subject in ('static','refined','original'):
            for material in ('nylon','aluminium'):
                case = f'snug125_{material}_{subject}'
                assert case in inputs
                yield case,inputs[case]['parent']
            if subject == 'static':
                yield 'snug125_nylon_mesh3_static',''
            if subject == 'original':
                for material in ('nylon','aluminium'):
                    yield f'snug125_{material}_original_sturm',''
        # Release matched film subjects early so the host can encode while the longer local pulls solve.
        branches=('snug125_nylon','snug125_aluminium')
        for subject in ('basis','modal20'):
            for branch in branches:
                case=branch+'_'+subject
                if case in inputs:
                    yield case,inputs[case]['parent']
        for axis in 'XYZ':
            for branch in branches:
                yield native_case(branch,'psd_'+axis),branch+'_basis'
            follow=ROOT/'validation/snug125/contact_refinement_inputs.json'
            if axis=='X' and follow.is_file():
                for name in read(follow):yield name,''
        refined_basis=ROOT/'validation/snug125/modal_refinement_input.json'
        if refined_basis.is_file():
            control=read(refined_basis)
            yield control['case'],control['parent']
        for branch in branches:
            yield branch+'_enforced',branch+'_basis'
        for axis in 'XYZ':
            for branch in branches:
                yield branch+'_motion_'+axis,branch+'_enforced'
        snug_dir=ROOT/'validation/snug125'
        local_suffix='_m15' if (snug_dir/'local_mesh15_preflight.json').is_file() else ''
        local_catalog=snug_dir/('local_inputs'+local_suffix+'.json')
        if local_catalog.is_file():
            for case,meta in read(local_catalog).items():
                yield meta['bare_reference'],''
                yield case,meta['bare_reference']
        aluminium=ROOT/'validation/snug125/aluminium_refinement_inputs.json'
        if aluminium.is_file():
            for case,spec in read(aluminium).items():
                yield case,spec['parent']
        tolerance=ROOT/'validation/snug125/force_tolerance_input.json'
        if tolerance.is_file():
            control=read(tolerance)
            yield control['case'],''
        for branch in branches:
            patch_series=ROOT/'validation/snug125'/(branch+'_patch_inputs.json')
            if patch_series.is_file():
                for case,spec in read(patch_series).items():
                    yield case,spec['free_reference'] if spec['contact'] else branch+'_basis'
        for branch in branches:
            registry=ROOT/'validation/snug125'/(branch+'_shell_inputs_v2.json')
            if registry.is_file():
                for name,spec in read(registry).items():
                    parent=f'shell_{branch}_free_v2' if spec['contact'] else branch+'_basis'
                    yield name,parent
        sensitivities=snug_dir/('local_sensitivity_inputs'+local_suffix+'.json')
        if sensitivities.is_file():
            for case,meta in read(sensitivities).items():
                yield meta['bare_reference'],''
                yield case,meta['bare_reference']
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
            if (ROOT/'validation/default_contact_jobs.json').exists():
                for mesh in ('refined','original'):
                    install=f'{branch}_default_{mesh}_static'
                    yield install,''
                    yield native_case(branch,mesh),install
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
                # Both remaining default-contact film subjects use the same refined extraction.
                for raised in ('stand3_nylon','stand3_aluminium'):
                    yield raised+'_refined',''
                # Interleave the original signed-motion comparison with the two long installations.
                yield 'bare_enforced','bare_basis'
                for direction in 'XYZ':yield 'bare_motion_'+direction,'bare_enforced'
                yield 'stand3_aluminium_lateral_friction_locked_pin1','bare_lateral_friction_locked'
                for direction in 'YZ':
                    for raised in ('stand3_nylon','stand3_aluminium'):
                        yield native_case(raised,'psd_'+direction),raised+'_basis'
                yield 'bare_damage_cont_nominal',''
                # Compare the two whole-board flush installations before a second long local drawdown.
                if (ROOT/'validation/board_surface_jobs.json').exists():
                    yield 'flush_aluminium_surf1_static',''
                # Complete the native raised movie histories after the aluminium installation.
                # Both accepted modal bases and all six native PSD comparisons precede them.
                for raised in ('stand3_nylon','stand3_aluminium'):
                    yield raised+'_enforced',raised+'_basis'
                    for direction in 'XYZ':yield raised+'_motion_'+direction,raised+'_enforced'
                for raised in ('stand3_nylon','stand3_aluminium'):
                    yield raised+'_damage_cont_nominal_pin1','bare_damage_cont_nominal'
                # Repeat the three October material-law controls alongside the primary damage fixtures.
                if (ROOT/'validation/coupon_reference/october.json').is_file():
                    for control in ('nominal_v4','uniform','unsym'):
                        yield 'bare_damage_coupon_'+control,''
                resolution=ROOT/'validation/common_pull_resolution.json'
                if resolution.is_file():
                    for name,control in read(resolution).items():
                        yield name,control['parent']
                # Complete the original signed frictional pull for the bare and both raised fixtures.
                reverse='lateral_friction_locked_minus'
                yield 'bare_'+reverse,''
                for raised in ('stand3_nylon','stand3_aluminium'):
                    yield raised+'_'+reverse+'_pin1','bare_'+reverse
                detection=ROOT/'validation/pull_detection_control.json'
                if detection.is_file():
                    for name,control in read(detection).items():
                        yield name,control['parent']
                if (ROOT/'validation/local_seat_jobs.json').is_file():
                    yield 'flush_nylon_lateral_friction_locked_seatfaces1','bare_lateral_friction_locked'
                    if (ROOT/'validation/rocking_bearing_input.json').is_file():
                        yield 'flush_nylon_lateral_friction_locked_rock1_seatfaces1','bare_lateral_friction_locked'
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
    refinement=ROOT/'validation/case_refinement_inputs.json'
    if refinement.is_file():
        branch=read(refinement)['branch']
        yield branch+'_static',''
        yield branch+'_basis',branch+'_static'
        yield native_case(branch,'psd_X'),branch+'_basis'
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

    grip=ROOT/'validation/perfect_grip_cases.json'
    if grip.is_file():
        for case,spec in read(grip).items():
            yield case,'bare_'+spec['source']


    variants=ROOT/'validation/damage_variant_inputs.json'
    if variants.is_file():
        for case,spec in read(variants).items():
            yield case,'bare_'+spec['source']


def damage_reference_ready(spec):
    """Use the nominal case's audited local loading path before dispatching its conditional variations."""
    case=spec['nominal']
    if case.startswith(('stand3_','snug125_')):
        scope=ROOT/'validation/pulls'/(case+'_damage_scope.json')
        return scope.is_file() and read(scope)['case']==case
    from audit_local import table
    material_path=ROOT/'validation/installation_material'/(case+'.json')
    verdicts=[ROOT/'validation'/k/(case+'.json') for k in ('local','partial_local','review_local')]
    available=[p for p in verdicts if p.is_file()]
    if len(available)!=1 or not material_path.is_file():
        return False
    result=read(available[0])
    material=read(material_path)
    assert result['case']==material['case']==case and result['rst_sha256']==material['rst_sha256']
    if not result['installed_state'] or any(k.startswith('all_') for k in material['first_reference_crossings']):
        return False
    # Only the clamping and installation stages govern this check. Later pull events have their own scope.
    records=table(RT/'post'/result['campaign']/case/'closed_contacts.csv')
    install=records[records['stage']<=3]
    limits=result['contact_resolution_limits_mm']
    if any(row['max_closed_penetration_mm']>limits[str(int(row['pair']))] for row in install):
        return False
    final=install[install['native_set']==install['native_set'].max()]
    seats=final[final['pair']>=880]
    gaps=result['installed_tab_gaps_mm']
    return (len(seats)==len(gaps)==4 and all(seats['closed']>0)
            and all(abs(row['min_mm'])<=result['tab_plane_review_screen_mm'] for row in gaps))


def result_path(case):
    if case.startswith('shell_snug125_'):
        return ROOT/'validation/shell_equilibrium'/(case+'.json')
    if case.startswith('replay_'):
        return ROOT/'validation/contact_replay'/(case+'.json')
    if case.startswith('patch_'):
        return ROOT/'validation/contact_patch'/(case+'.json')
    local='_lateral_' in case or '_damage_' in case
    category = 'motion' if case.endswith('_enforced') or '_motion_' in case else ('local' if local else 'global')
    return ROOT/'validation'/category/(case+'.json')

def ordered_jobs():
    # Repeated priorities must refer to the same physical case and prerequisite.
    parents={}
    for name,parent in jobs():
        if name in parents and parents[name]!=parent:raise ValueError('Conflicting parent for '+name)
        parents[name]=parent
    sequence=list(parents.items())
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
                dispatch_solver('flush_install_check.ps1',['-Trial',probe.name],probe)
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
        if case in ('stand3_aluminium_psd_X_private1','flush_nylon_surf1_static') and not (RECEIPTS/case/'dispatch.json').exists():
            controls.append(('shared_dmp_io_v1','control.inp','shared_dmp_control','shared_dmp_control.ps1','shared_dmp_control.py'))
        if case=='stand3_nylon_enforced' and not (RECEIPTS/case/'dispatch.json').exists():
            controls.append(('spherical_bearing_control_v1','control.inp','spherical_bearing_control','actuator_control.ps1','rocking_bearing.py'))
        if controls:
            # These short checks are serial native jobs; a known numerical rejection only
            # holds the installation branch. An ambiguous live job blocks further dispatch.
            for name,inp,publication,runner,auditor in controls:
                probe=RT/name
                if not (probe/inp).is_file() or (ROOT/f'validation/{publication}.json').exists():continue
                if shutil.disk_usage(ROOT).free<400_000_000_000:raise RuntimeError('Host storage reserve reached')
                if not (probe/'exit.txt').exists() and not (probe/'failed.txt').exists():
                    dispatch_solver(runner,['-Trial',name],probe)
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
        if case.startswith('snug125_') and case.endswith('_original_sturm') and not (receipt/'dispatch.json').exists():
            source=case.removesuffix('_sturm')
            if result_path(source).is_file() or not (RECEIPTS/source/'audit_failed.txt').is_file():continue
            from prepare_modal_retry import prepare
            try:
                prepare(source,CAMPAIGN)
            except ValueError as exc:
                log(f'Default-mesh control requires inspection for {source}: {exc}')
                continue
        final=result_path(case)
        partial=ROOT/'validation/partial_local'/(case+'.json')
        review=ROOT/'validation/review_local'/(case+'.json')
        if final.exists() or partial.exists() or review.exists() or (ROOT/'validation/review_global'/(case+'.json')).exists():continue
        if parent and not result_path(parent).is_file() and not (ROOT/'validation/partial_local'/(parent+'.json')).is_file():
            log('Parent unaccepted: '+case);continue
        if case.startswith('shell_snug125_') and (ROOT/'validation/review_shell_equilibrium'/(case+'.json')).is_file():
            continue
        if case.startswith('patch_snug125_') and (ROOT/'validation/review_contact_patch'/(case+'.json')).is_file():
            continue
        if case.startswith('snug125_') and parent.endswith('_static'):
            review=ROOT/'validation/snug125'/f'{parent}_installed.json'
            if not review.is_file() or not read(review)['linearization_review_passed']:
                log('Snug prestressed comparison awaits its installed-state review: '+case)
                continue
        if not case.startswith('bare_') and not (ROOT/'validation/cased_preflight.json').is_file():
            raise RuntimeError('Cased preflight review pending')
        if '_default_' in case and case.startswith('flush_'):
            mesh=case.split('_default_',1)[1].split('_')[0]
            if not (ROOT/f'validation/default_{mesh}_initial.json').is_file():
                log('Default-contact geometry check pending: '+case)
                continue
        damage_catalog=ROOT/'validation/damage_variant_inputs.json'
        if case.startswith('snug125_'):
            name='local_sensitivity_inputs_m15.json' if case.endswith('_m15') else 'local_sensitivity_inputs.json'
            damage_catalog=ROOT/'validation/snug125'/name
        if '_damage_cont' in case and not case.startswith('bare_') and damage_catalog.is_file():
            variation=read(damage_catalog).get(case)
            if variation and not damage_reference_ready(variation):
                log('Nominal damage fixture has no supported starting path for this variation: '+case)
                continue
        if case.endswith('_rock1_seatfaces1'):
            source=case.replace('_rock1_seatfaces1','_seatfaces1')
            checked=[ROOT/'validation'/key/(source+'.json') for key in ('local','partial_local','review_local')]
            if not any(p.is_file() for p in checked) or not (ROOT/'validation/spherical_bearing_control.json').is_file():
                log('Bearing sensitivity awaits its matched rigid fixture and joint control: '+case)
                continue
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
        if not (receipt/'dispatch.json').exists():recover_split_readbacks()
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
            if case.startswith(('patch_','replay_','shell_snug125_')):
                flags.extend(['-Cores','2'])
            elif parent and not local:
                flags.extend(['-Parent',parent])
            log('Dispatch '+case);dispatch_solver('native_run.ps1',flags,receipt)
        while not state.is_file():time.sleep(15)
        while True:
            current=read(state)
            if current['phase'] in ('solver_complete','failed'):break
            if current.get('shared_scratch'):
                free=shutil.disk_usage(ROOT).free
                if free<425_000_000_000:
                    stop=receipt/('host_critical.json' if free<400_000_000_000 else 'host_stop.json')
                    if not stop.exists():save(stop,dict(case=case,free_bytes=free,utc=utc()))
            time.sleep(15)
        if current['phase']=='failed':
            log('Failed native '+case)
            capture_closed_installation(case,current,receipt)
            continue
        if not (receipt/'released.txt').exists():
            log('Archive '+case)
            archive_closed_case(case,receipt)
        audit='audit_board_surface.py' if case.endswith('_surf1_static') else ('audit_install.py' if case.endswith(('_approach1','_seatfaces1')) else ('audit_local.py' if local else 'audit_global.py'))
        if '_default_' in case and case.endswith('_static'):
            audit='audit_default_install.py'
        if case.startswith('shell_snug125_'):
            audit='audit_snug_shell.py'
        elif case.startswith('patch_'):
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

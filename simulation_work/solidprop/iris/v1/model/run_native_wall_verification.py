"""Guarded, one-at-a-time launch and collection of the new native verification cases.

No job is dispatched by readiness or check-wrapper. An existing runtime always
requires inspection or collection. An ambiguous launch is never repeated.
"""
import argparse
import base64
import fcntl
import json
import subprocess
import sys
import time
import uuid

import audit_native_moving_char as moving
import audit_native_conduction_mode as mode
import native_snapshot_verification as snapshots
import audit_native_cf_tail as tail
from continuous_heating_campaign import digest
from ops import ROOT, TMP, UNC, StorageLimitError, atomic, disks, guest, stop_runs, utc

CF='sustainer_cf_pulse7_midpoint_joint320_geom005_smp10'
NATIVE_GUARD=r"""$solvers=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -match '^(ANSYS(?:\d+)?|mpiexec|hydra_pmi_proxy)\.exe$'})
if($solvers.Count){throw 'Another native solver or wrapper is active'}
"""


def spec(case):
    if case=='annular':
        return mode.PACKAGE,mode.RUN,'irmode64',mode.DECK,[mode.LOG,'mode_time.txt','mode_end.txt']
    if case in tail.JOBS:
        return tail.PACKAGE,TMP/'runs'/('cf_tail_'+case),case,case+'.inp',[case+'.out','tail_steps.txt','tail_field.txt']
    if case in snapshots.CASES:
        return snapshots.PACKAGE,TMP/'runs'/('snapshot_r2_'+case),case,case+'.inp',[case+'.out','snap_field.txt']
    job='mvchar'+case.removeprefix('char')
    return moving.PACKAGE,TMP/'runs'/('moving_char_log_r2_'+job),job,job+'.inp',[job+'.out','moving_steps.txt','moving_field.txt']


def expected_sha(case,package,job):
    name='expected.json' if case=='annular' else job+'.json'
    data=json.loads((package/name).read_text())
    return data['input_sha256'] if case=='annular' else data['deck_sha256']


def prerequisites(case):
    reasons=[]
    p=ROOT/'validation'
    required=[p/f'queue_{CF}.json',p/f'accepted_{CF}.json',p/f'native_pulse_comparison_{CF}.json']
    if not all(x.is_file() for x in required):
        reasons.append('CF320 terminal receipts pending')
    else:
        queue,accepted,comp=(json.loads(x.read_text()) for x in required)
        if not (len(queue)==1 and queue[0]['runtime']==CF and accepted['passed'] and
                comp['comparison_passed'] and comp['native_control_checks_passed'] and
                comp['persistent_native_topology_passed'] and comp['cooling_transition_passed'] and
                queue[0]['accepted_index']==accepted['accepted_steps'] and
                accepted['time_s']==queue[0]['time_s']==comp['accepted_native_time_s']):
            reasons.append('CF320 terminal identities or controls failed review')
    if case!='annular':
        f=p/'native_annular_mode64_smp10.json'
        if not f.is_file() or not json.loads(f.read_text()).get('passed'):
            reasons.append('Annular benchmark acceptance pending')
    if case=='char16' or case in snapshots.CASES:
        f=p/'native_moving_char_r2_mvchar8.json'
        if not f.is_file() or not json.loads(f.read_text()).get('passed'):
            reasons.append('Coarse moving-char acceptance pending')
    if case in snapshots.CASES:
        prior = ['native_moving_char_r2_mvchar16'] + ['native_snapshot_r2_'+s for s in snapshots.CASES[:snapshots.CASES.index(case)]]
        for name in prior:
            record = p/(name+'.json')
            if not record.is_file() or not json.loads(record.read_text()).get('passed'):
                reasons.append('Pending acceptance of '+name)
    if case in tail.JOBS:
        prior = ['native_snapshot_r2_'+s for s in snapshots.CASES]
        prior += ['native_cf_terminal_window_'+job for job in tail.JOBS[:tail.JOBS.index(case)]]
        for name in prior:
            record = p/(name+'.json')
            if not record.is_file() or not json.loads(record.read_text()).get('passed'):
                reasons.append('Pending acceptance of '+name)
    return reasons


def wrapper(run, job, deck, files, sha, nonce):
    win=r'C:\IrisStudy\runs'+'\\'+run.name
    share=UNC+r'\ansystmp\runs'+'\\'+run.name
    script=r"""$ErrorActionPreference='Stop'
$root='@WIN@'
$share='@SHARE@'
$deck='@DECK@'
$nonce='@NONCE@'
$job='@JOB@'
try {
 @GUARD@
 $disk=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
 $guard=Get-Content -LiteralPath '@MONITOR@' -Raw | ConvertFrom-Json
 $now=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
 if ((Test-Path -LiteralPath '@STOP@') -or (Test-Path -LiteralPath ($share+'\PAUSE_REQUESTED')) -or
     -not $guard.allowed -or ($now-$guard.checked_epoch) -gt 45 -or
     $guard.mac_free_bytes -lt 400000000000 -or $disk.FreeSpace -lt 10000000000) {throw 'Storage guard'}
 $deckhash=(Get-FileHash -LiteralPath ($root+'\'+$deck) -Algorithm SHA256).Hash
 if($deckhash -ne '@SHA@'){throw 'Guest deck hash differs'}
 $env:ANSYSLMD_LICENSE_FILE='1055@localhost'
 $solver=Start-Process -FilePath 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -WorkingDirectory $root -ArgumentList @('-b','-smp','-np','10','-p','ansys','-j',$job,'-i',$deck,'-o',($job+'.out')) -Wait -PassThru
 $export=@{}
 foreach($name in @(@FILES@)) {
   $p=Join-Path $root $name
   if(Test-Path -LiteralPath $p) {
     $export[$name]=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
     Copy-Item -LiteralPath $p -Destination (Join-Path $share $name)
   }
 }
 $end=@{job=$job;nonce=$nonce;exit_code=$solver.ExitCode;guest_input_sha256=$deckhash;guest_sha256=$export;utc=[DateTime]::UtcNow.ToString('o')}
 $end|ConvertTo-Json|Set-Content -Encoding UTF8 -LiteralPath ($share+'\guest_terminal.tmp')
 Move-Item -LiteralPath ($share+'\guest_terminal.tmp') -Destination ($share+'\guest_terminal.json')
} catch {
 @{error=$_.ToString();nonce=$nonce;utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath ($share+'\guest_failure.json')
 exit 1
}
"""
    for key,value in dict(WIN=win,SHARE=share,JOB=job,DECK=deck,NONCE=nonce,GUARD=NATIVE_GUARD,SHA=sha,
            MONITOR=UNC+r'\ansystmp\host_storage_status.json',STOP=UNC+r'\ansystmp\STOP_WORK.json',
            FILES=','.join("'"+f+"'" for f in files)).items():
        script=script.replace('@'+key+'@',value)
    return script


def check_wrapper(script):
    encoded=base64.b64encode(script.encode()).decode()
    reply=guest("$src=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"'));"
                "$tokens=$null;$err=$null;[void][Management.Automation.Language.Parser]::ParseInput($src,[ref]$tokens,[ref]$err);"
                "if($err.Count){throw ($err.Message -join '; ')};'PARSE_OK'")
    if reply!='PARSE_OK': raise RuntimeError(reply)


def check_idle(case,run):
    reasons=prerequisites(case)
    registry=json.loads((TMP/'active_runs.json').read_text())
    if registry: reasons.append('A study runtime is registered')
    if run.exists(): reasons.append('Dedicated host runtime exists; inspect or collect')
    ps=subprocess.check_output(['ps','-Ao','command='],text=True)
    if str(ROOT/'model/run_queue.py')+' ' in ps: reasons.append('Native queue observer is live')
    watcher=(TMP/'storage_guard.pid').read_text().strip()
    watch=subprocess.run(['ps','-p',watcher,'-o','command='],capture_output=True,text=True)
    if 'ops.py watch' not in watch.stdout or time.time()-json.loads((TMP/'host_storage_status.json').read_text())['checked_epoch']>45:
        reasons.append('Storage watcher is missing or stale')
    if not reasons: guest("$ErrorActionPreference='Stop';"+NATIVE_GUARD)
    return reasons


def launch(case,package,run,job,deck,files,sha):
    problems=check_idle(case,run)
    if problems: raise RuntimeError('; '.join(problems))
    nonce=uuid.uuid4().hex
    script=wrapper(run,job,deck,files,sha,nonce)
    check_wrapper(script)
    # An exclusive new host directory is the durable no-retry marker. Register
    # it before the first guest write so the watcher always knows the job name.
    disks()
    run.mkdir()
    (run/deck).write_bytes((package/deck).read_bytes())
    (run/'dispatch.ps1').write_text(script,encoding='utf-8-sig')
    win=r'C:\IrisStudy\runs'+'\\'+run.name
    share=UNC+r'\ansystmp\runs'+'\\'+run.name
    entry=dict(job=job,relative_runtime=str(run.relative_to(ROOT)),windows_root=win)
    atomic(run/'intent.json',dict(nonce=nonce,utc=utc(),case=case,deck_sha256=sha))
    atomic(TMP/'active_runs.json',[entry])
    # Every path and identifier comes from spec(), never arbitrary CLI paths.
    cmd="$ErrorActionPreference='Stop';"+NATIVE_GUARD+f"$root='{win}';$share='{share}';"
    cmd+="if(Test-Path -LiteralPath $root){throw 'Guest runtime exists'};New-Item -ItemType Directory -Path $root | Out-Null;"
    cmd+=f"Copy-Item -LiteralPath ($share+'\\{deck}') -Destination ($root+'\\{deck}');"
    cmd+="Copy-Item -LiteralPath ($share+'\\dispatch.ps1') -Destination ($root+'\\dispatch.ps1');"
    cmd+="$line='powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File '+$root+'\\dispatch.ps1';"
    cmd+="$p=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$line;CurrentDirectory=$root};"
    cmd+="if($p.ReturnValue -ne 0){throw 'Guest wrapper launch failed'};"
    cmd+=f"@{{ProcessId=$p.ProcessId;ReturnValue=$p.ReturnValue;nonce='{nonce}'}}|ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath ($share+'\\guest_launch.json');$p.ProcessId"
    # An ambiguous WMI response leaves the intent and registry intact. The
    # receipt and guest process are inspected on the next continuation.
    print(guest(cmd))


def collect(case,run,job):
    receipt=json.loads((run/'guest_terminal.json').read_text(encoding='utf-8-sig'))
    intent=json.loads((run/'intent.json').read_text())
    launch_proof=json.loads((run/'guest_launch.json').read_text(encoding='utf-8-sig'))
    assert intent['nonce']==receipt['nonce']==launch_proof['nonce'] and launch_proof['ReturnValue']==0
    guest("$ErrorActionPreference='Stop';"+NATIVE_GUARD)
    registry=json.loads((TMP/'active_runs.json').read_text())
    if registry and (len(registry)!=1 or registry[0]['job']!=job or registry[0]['relative_runtime']!=str(run.relative_to(ROOT))):
        raise RuntimeError('Registry belongs to another job')
    if case=='annular':
        subprocess.run([sys.executable,str(ROOT/'model/audit_native_conduction_mode.py'),'audit'],check=True)
    elif case in snapshots.CASES:
        snapshots.audit(case,run)
    elif case in tail.JOBS:
        tail.audit(case,run)
    else:
        moving.audit(int(case.removeprefix('char')))
    if registry: atomic(TMP/'active_runs.json',[])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('case',choices=('annular','char8','char16',*snapshots.CASES,*tail.JOBS))
    p.add_argument('action',choices=('readiness','check-wrapper','launch','collect'))
    args=p.parse_args()
    disks()
    package,run,job,deck,files=spec(args.case)
    sha=expected_sha(args.case,package,job)
    if digest(package/deck)!=sha: raise ValueError('Sealed native deck changed')
    if args.action=='check-wrapper':
        check_wrapper(wrapper(run,job,deck,files,sha,'check_only'))
        print('Guest PowerShell parsed the wrapper. No native launch.')
        return
    if args.action=='readiness':
        print(check_idle(args.case,run) or ['Ready'])
        return
    with (TMP/'native_wall_dispatch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='launch': launch(args.case,package,run,job,deck,files,sha)
        else: collect(args.case,run,job)


if __name__=='__main__':
    try: main()
    except StorageLimitError as exc:
        stop_runs(str(exc))
        raise

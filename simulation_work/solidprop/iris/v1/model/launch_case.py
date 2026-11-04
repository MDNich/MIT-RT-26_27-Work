"""Explicit asynchronous launch of one prepared runtime on the Windows VM."""
import argparse
import json
from ops import ROOT, TMP, atomic, disks, guest, utc

def main():
    p=argparse.ArgumentParser()
    p.add_argument('runtime')
    p.add_argument('phase',choices=['preflight','run','resume'])
    args=p.parse_args()
    status=disks()
    root=(TMP/'runs'/args.runtime).resolve()
    if root.parent != (TMP/'runs').resolve():
        raise ValueError('Runtime must be a direct child of ansystmp/runs')
    cfg=json.loads((root/'config.json').read_text())
    script=r"$ErrorActionPreference='Stop';$r=@(Get-CimInstance Win32_Process|Where-Object{$_.Name -match '^(ANSYS(?:\d+)?|mpiexec|hydra_pmi_proxy)\.exe$'});if($r.Count){throw 'Another solver is running'};"
    shared=cfg.get('host_runtime',cfg['windows_root'])
    script+="$root='"+cfg['windows_root']+"';$shared='"+shared+"';"
    if shared != cfg['windows_root']:
        if not cfg['windows_root'].startswith('C:\\IrisStudy\\runs\\'):
            raise ValueError('Guest-local outputs must stay in this study directory')
        script+="if(-not(Test-Path -LiteralPath $root)){New-Item -ItemType Directory -Force -Path (Split-Path $root)|Out-Null;Copy-Item -LiteralPath $shared -Destination $root -Recurse}else{if((Get-FileHash ($root+'\\input_manifest.json')).Hash -ne (Get-FileHash ($shared+'\\input_manifest.json')).Hash){throw 'Guest input mismatch'}};"
    flags = {'preflight':'-Preflight','run':'-Run','resume':'-Run -Resume'}[args.phase]
    sync="if($root -ne $shared){Copy-Item -Path ($root+'\\*') -Destination $shared -Recurse -Force};"
    wrapper = "$ErrorActionPreference='Stop';$root='"+cfg['windows_root']+"';$shared='"+shared+"';try { & ($root+'\\launch_v0.ps1') "+flags+" 1> ($root+'\\launcher_"+args.phase+".out') 2> ($root+'\\launcher_"+args.phase+".err');"+sync+"@{ok=$true;utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content ($shared+'\\phase_"+args.phase+"_exit.json') } catch {$errorText=$_.ToString();"+sync+"@{ok=$false;error=$errorText;utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content ($shared+'\\phase_"+args.phase+"_exit.json');exit 1}"
    wrapper_name='dispatch_'+args.phase+'.ps1'
    (root/wrapper_name).write_text(wrapper,encoding='utf-8-sig')
    # WMI creates an independent process, so prlctl does not wait for a long
    # descendant solve or retain the guest-execution lock throughout the job.
    command='powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File '+shared+'\\'+wrapper_name
    script+="$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='"+command+"';CurrentDirectory=$root};if($r.ReturnValue -ne 0){throw 'WMI launch failed'};$r|Select-Object ProcessId,ReturnValue|ConvertTo-Json"
    job='file' if args.phase!='preflight' else 'preflight'
    atomic(TMP/'active_runs.json',[dict(relative_runtime=str(root.relative_to(ROOT)),job=job,windows_root=cfg['windows_root'])])
    result=guest(script)
    atomic(root/('host_launch_'+args.phase+'.json'),dict(utc=utc(),disk_status=status,guest=result))
    print(result)

if __name__=='__main__':
    main()

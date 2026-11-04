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
    script+="$root='"+cfg['windows_root']+"';"
    flags = {'preflight':'-Preflight','run':'-Run','resume':'-Run -Resume'}[args.phase]
    wrapper = "$ErrorActionPreference='Stop';$root='"+cfg['windows_root']+"';try { & ($root+'\\launch_v0.ps1') "+flags+" 1> ($root+'\\launcher_"+args.phase+".out') 2> ($root+'\\launcher_"+args.phase+".err');@{ok=$true;utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content ($root+'\\phase_"+args.phase+"_exit.json') } catch {@{ok=$false;error=$_.ToString();utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content ($root+'\\phase_"+args.phase+"_exit.json');exit 1}"
    wrapper_name='dispatch_'+args.phase+'.ps1'
    (root/wrapper_name).write_text(wrapper,encoding='utf-8-sig')
    # WMI creates an independent process, so prlctl does not wait for a long
    # descendant solve or retain the guest-execution lock throughout the job.
    command='powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File '+cfg['windows_root']+'\\'+wrapper_name
    script+="$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='"+command+"';CurrentDirectory=$root};if($r.ReturnValue -ne 0){throw 'WMI launch failed'};$r|Select-Object ProcessId,ReturnValue|ConvertTo-Json"
    job='file' if args.phase!='preflight' else 'preflight'
    atomic(TMP/'active_runs.json',[dict(relative_runtime=str(root.relative_to(ROOT)),job=job)])
    result=guest(script)
    atomic(root/('host_launch_'+args.phase+'.json'),dict(utc=utc(),disk_status=status,guest=result))
    print(result)

if __name__=='__main__':
    main()

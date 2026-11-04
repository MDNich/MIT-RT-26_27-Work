"""Launch a tiny native no-solve probe in an isolated, registered runtime."""
from pathlib import Path
import json
from ops import ROOT, TMP, atomic, disks, guest, utc

def main():
    status = disks()
    runtime = TMP / 'runs' / 'environment_probe'
    runtime.mkdir(parents=True, exist_ok=True)
    if list(runtime.glob('*.out')):
        raise RuntimeError('Probe already has output; inspect it before choosing a new directory.')
    (runtime / 'probe.inp').write_text('/BATCH\n/PREP7\n/UNITS,MKS\nET,1,278\nMP,KXX,1,1\nMP,C,1,1000\nMP,DENS,1,1000\nBLOCK,0,.001,0,.001,0,.001\nESIZE,.001\nVMESH,ALL\n*GET,NN,NODE,0,COUNT\n*GET,NE,ELEM,0,COUNT\n*VWRITE,NN,NE\n(\'IRIS_PROBE NODES=\',F12.0,\' ELEMENTS=\',F12.0)\n/COM,IRIS_NATIVE_PREFLIGHT_NO_SOLVE\nFINISH\n/EXIT,NOSAVE\n')
    atomic(TMP / 'active_runs.json', [dict(relative_runtime='ansystmp/runs/environment_probe', job='probe')])
    script = r'''
$ErrorActionPreference='Stop'
$root='I:\ansystmp\runs\environment_probe'
$running=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -match '^(ANSYS(?:\d+)?|mpiexec|hydra_pmi_proxy)\.exe$'})
if($running.Count){throw 'A solver is already running'}
$env:ANSYSLMD_LICENSE_FILE='1055@localhost'
$args=@('-b','-smp','-np','1','-p','ansys','-j','probe','-i','probe.inp','-o','probe.out')
$p=Start-Process -FilePath 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -WorkingDirectory $root -ArgumentList $args -PassThru
[pscustomobject]@{ProcessId=$p.Id;Runtime=$root;StartedUtc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json
'''
    launched = guest(script)
    atomic(runtime / 'launch.json', dict(started_utc=utc(), guest_output=launched, disk_status=status))
    print(launched)

if __name__ == '__main__':
    main()

param([Parameter(Mandatory)][ValidateSet('board_actuator_control_v1','seat_surface_control_v1','patch_table_control_v1')][string]$Trial)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$src="$root\.runtime\$Trial"
$work="C:\Temp\PBCaseStudy\$Trial"
$exe='C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
$env:ANSYSLMD_LICENSE_FILE='1055@localhost'
try {
    if ((Get-PSDrive C).Free -lt 18000000000 -or (Test-Path $work)){throw 'Guard or existing test; inspect before retrying'}
    $active=@(Get-Process -ea SilentlyContinue|Where-Object {$_.ProcessName -match '^(ANSYS|ANSYS\d+|mapdl|mpiexec|hydra_pmi_proxy)$'})
    if ($active.Count){throw 'Another solver is active'}
    New-Item -ItemType Directory $work|Out-Null
    Copy-Item -LiteralPath "$src\control.inp" -Destination $work
    if ((Get-FileHash "$src\control.inp").Hash -ne (Get-FileHash "$work\control.inp").Hash){throw 'Staging mismatch'}
    if ($Trial -eq 'patch_table_control_v1'){
        $meta=Get-Content -LiteralPath "$root\validation\patch_table_control_input.json" -Raw|ConvertFrom-Json
        foreach($entry in $meta.files.PSObject.Properties){
            if ($entry.Name -notmatch '^[a-z]+\.dat$|^control\.inp$'){throw 'Unexpected control input'}
            if ($entry.Name -ne 'control.inp'){Copy-Item -LiteralPath (Join-Path $src $entry.Name) -Destination $work}
            if ((Get-FileHash -LiteralPath (Join-Path $work $entry.Name)).Hash -ne $entry.Value){throw 'Control input mismatch'}
        }
    }
    $p=Start-Process $exe -WorkingDirectory $work -Wait -PassThru -ArgumentList '-b nolist -s noread -p ansys -smp -np 1 -j file -i control.inp -o control.out'
    foreach ($n in 'control.out','file.err','actuator_static.csv','actuator_modal.csv','seat_control.csv','control_response.csv'){
        if (Test-Path "$work\$n"){Copy-Item "$work\$n" -Destination $src}
    }
    $p.ExitCode|Set-Content "$src\exit.txt" -Encoding UTF8
} catch {$_.Exception.Message|Set-Content "$src\failed.txt";throw}

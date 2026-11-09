param([Parameter(Mandatory)][ValidateSet('search01','search02')] [string]$Series)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$env:ANSYSLMD_LICENSE_FILE='1055@localhost'
$exe='C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
foreach($case in 'stand3_nylon_lateral_friction_locked','stand3_nylon_static','flush_nylon_lateral_friction_locked','flush_nylon_static'){
    $src="$root\.runtime\contact_checks\$case"
    $d="C:\Temp\PBCaseStudy\${Series}_$case"
    if ((Get-PSDrive C).Free -lt 18000000000 -or (Test-Path $d) -or (Test-Path "$src\exit.txt")) {throw "Preflight guard $case"}
    $active=@(Get-Process -ea SilentlyContinue | Where-Object { $_.ProcessName -match '^(ANSYS|ANSYS\d+|mapdl|mpiexec|hydra_pmi_proxy)$' })
    if ($active.Count -ne 0){throw 'Another solver is active'}
    New-Item -ItemType Directory $d|Out-Null
    Copy-Item -LiteralPath "$src\pre.inp" -Destination $d
    if ((Get-FileHash "$src\pre.inp").Hash -ne (Get-FileHash "$d\pre.inp").Hash){throw 'Staging mismatch'}
    $p=Start-Process $exe -WorkingDirectory $d -Wait -PassThru -ArgumentList '-b nolist -s noread -p ansys -smp -np 1 -j pre -i pre.inp -o pre.out'
    foreach($n in 'pre.out','pre.err'){if(Test-Path "$d\$n"){Copy-Item "$d\$n" -Destination $src}}
    $p.ExitCode|Out-File "$src\exit.txt"
    if ($p.ExitCode -ne 0){throw "Preflight failed: $case"}
}

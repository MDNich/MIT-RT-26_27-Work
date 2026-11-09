param([Parameter(Mandatory)][ValidateSet('flush_approach_v1','board_initial_v1','board_surface_initial_v1','local_seat_faces_v1','default_refined_initial_v1','default_original_initial_v1')] [string]$Trial)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$env:ANSYSLMD_LICENSE_FILE='1055@localhost'
$exe='C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
$src="$root\.runtime\$Trial"
$d="C:\Temp\PBCaseStudy\$Trial"
try {
    if ((Get-PSDrive C).Free -lt 18000000000 -or (Test-Path $d) -or (Test-Path "$src\exit.txt")) {throw 'Preflight guard'}
    $active=@(Get-Process -ea SilentlyContinue | Where-Object { $_.ProcessName -match '^(ANSYS|ANSYS\d+|mapdl|mpiexec|hydra_pmi_proxy)$' })
    if ($active.Count){throw 'Another solver is active'}
    New-Item -ItemType Directory $d|Out-Null
    Copy-Item -LiteralPath "$src\pre.inp" -Destination $d
    if ((Get-FileHash "$src\pre.inp").Hash -ne (Get-FileHash "$d\pre.inp").Hash){throw 'Staging mismatch'}
    $p=Start-Process $exe -WorkingDirectory $d -Wait -PassThru -ArgumentList '-b nolist -s noread -p ansys -smp -np 1 -j pre -i pre.inp -o pre.out'
    foreach($n in 'pre.out','pre.err','inventory.csv','board_inventory.csv','seat_faces.csv','seat_inventory.csv'){if(Test-Path "$d\$n"){Copy-Item "$d\$n" -Destination $src}}
    $p.ExitCode|Out-File "$src\exit.txt"
} catch {
    $_.Exception.Message|Out-File "$src\failed.txt"
    throw
}

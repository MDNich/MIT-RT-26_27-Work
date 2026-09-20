param([switch]$Run, [switch]$Resume, [switch]$PreflightMapdl)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$cfg = Get-Content -Raw (Join-Path $root 'config.json') | ConvertFrom-Json
if ($root.TrimEnd('\') -ne $cfg.windows_root.TrimEnd('\')) {
    throw "Use the prepared Windows folder $($cfg.windows_root)."
}
if ($Resume -and -not $Run) { throw '-Resume also requires explicit -Run.' }
if ($Run -and $PreflightMapdl) { throw 'Choose preflight OR simulation, not both.' }
$python = 'C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe'
$ansys = 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
foreach ($file in @($python,$ansys,(Join-Path $root 'source\usermatthLib.dll'))) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing $file" }
}
Push-Location $root
try {
    & $python -B package_check.py
    if ($LASTEXITCODE -ne 0) { throw 'Package verification failed.' }
    & $python -B coupler.py validate --root $root
    if ($LASTEXITCODE -ne 0) { throw 'Configuration verification failed.' }
    if (-not $Run -and -not $PreflightMapdl) {
        Write-Output 'PREPARED_NOT_STARTED. No MAPDL process started. -Run is required to solve.'
        return
    }
    $existing = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -in @('ANSYS.exe','mpiexec.exe','hydra_pmi_proxy.exe')
    })
    if ($existing.Count) { throw 'An ANSYS/MPI calculation already exists; nothing started.' }
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connect = $client.BeginConnect('localhost',1055,$null,$null)
        if (-not $connect.AsyncWaitHandle.WaitOne(3000)) { throw 'Local license server unavailable.' }
        $client.EndConnect($connect)
    } finally { $client.Close() }
    $env:ANSYSLMD_LICENSE_FILE = '1055@localhost'
    $env:ANS_USER_PATH = Join-Path $root 'source'
    $env:ANS_USER_PATH_261 = $env:ANS_USER_PATH
    $env:ANS_USE_UPF = ''
    if ($PreflightMapdl) {
        # This input has no SOLVE. It uses a separate job name and output folder.
        $inputPath = Join-Path $root 'preflight_no_solve.inp'
        if (Select-String -Path $inputPath -Pattern '^\s*SOLVE\b' -Quiet) { throw 'Unsafe preflight input.' }
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $log = Join-Path $root "validation\preflight_$stamp.out"
        $proc=Start-Process -FilePath $ansys -WorkingDirectory $root -ArgumentList @('-b','-smp','-np','1','-p','ansys','-j',"preflight_$stamp",'-i',$inputPath,'-o',$log) -PassThru -Wait
        if ($proc.ExitCode -ne 0) { throw "MAPDL preflight failed ($($proc.ExitCode)); see $log" }
        & $python -B verify_preflight.py --log $log
        if ($LASTEXITCODE -ne 0) { throw 'MAPDL preflight validation failed.' }
        return
    }
    if (-not (Test-Path 'validation\mapdl_preflight.json')) { throw 'Run -PreflightMapdl before -Run.' }
    $checked=Get-Content -Raw 'validation\mapdl_preflight.json' | ConvertFrom-Json
    $manifestHash=(Get-FileHash 'validation\input_manifest.json' -Algorithm SHA256).Hash.ToLower()
    if ($checked.input_manifest_sha256 -ne $manifestHash) { throw 'Inputs changed since native preflight.' }
    if ($Resume) {
        $state = Get-Content -Raw 'state.json' | ConvertFrom-Json
        if ($state.status -ne 'PAUSED_AT_CHECKPOINT' -or $state.index -lt 1) {
            throw 'Automatic resume is only allowed from a clean, accepted pause. Preserve and inspect any failed run.'
        }
        if (Test-Path 'coupler_error.txt') { throw 'Coupling failure present; resume is blocked.' }
        foreach ($suffix in @('rdb','ldhi','rth')) {
            if (-not (Test-Path "file.$suffix")) { throw "Missing file.$suffix" }
        }
        $common = $null
        for ($rank=0; $rank -lt 10; $rank++) {
            $names = @(Get-ChildItem -File -Filter "file$rank.r???" | Where-Object {$_.Extension -match '^\.r\d{3}$'} | ForEach-Object {$_.Extension})
            if (-not $names.Count) { throw "Missing rank $rank restart files." }
            if ($null -eq $common) { $common=$names } else { $common=@($common | Where-Object {$_ -in $names}) }
        }
        if (-not $common.Count) { throw 'No complete ten-rank restart generation.' }
        if (Test-Path 'PAUSE_REQUESTED') { Remove-Item -LiteralPath 'PAUSE_REQUESTED' }
        $input = 'resume_iteration4.inp'
    } else {
        if ((Test-Path 'state.json') -or @(Get-ChildItem -File -Filter 'file.*').Count) {
            throw 'Existing run preserved. Do not overwrite it: resume a clean pause or use a new folder.'
        }
        & $python -B coupler.py initialize --root $root
        if ($LASTEXITCODE -ne 0) { throw 'Initialization failed.' }
        $input = 'run_iteration4.inp'
    }
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $log = Join-Path $root "solve_$stamp.out"
    Write-Output "Explicit launch: $input; 10 ranks; local license; log=$log"
    $proc=Start-Process -FilePath $ansys -WorkingDirectory $root -ArgumentList @('-b','-dis','-np','10','-p','ansys','-j','file','-i',(Join-Path $root $input),'-o',$log) -PassThru -Wait
    if ($proc.ExitCode -ne 0) { throw "MAPDL exited with $($proc.ExitCode); preserve results and inspect $log." }
    Get-Content -Raw 'state.json' | ConvertFrom-Json | Select-Object index,time_s,status,layer
} finally { Pop-Location }

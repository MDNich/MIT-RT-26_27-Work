param([switch]$Run, [switch]$Resume, [switch]$Preflight)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$cfg = Get-Content -Raw (Join-Path $root 'config.json') | ConvertFrom-Json
if ($root.TrimEnd('\') -ne $cfg.windows_root.TrimEnd('\')) {
    throw "Launch from the prepared mapped folder $($cfg.windows_root), not $root."
}
if ($Resume -and -not $Run) { throw '-Resume also requires -Run.' }
if ($Run -and $Preflight) { throw 'Choose preflight or simulation, not both.' }

$python = 'C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe'
$ansys = 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
foreach ($file in @($python, $ansys, (Join-Path $root 'usermatthLib.dll'))) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing required file: $file" }
}

Push-Location $root
try {
    & $python -B package_check.py
    if ($LASTEXITCODE -ne 0) { throw 'Input package hash verification failed.' }
    & $python -B coupler.py validate --root $root
    if ($LASTEXITCODE -ne 0) { throw 'Configuration or mesh validation failed.' }
    if (-not $Run -and -not $Preflight) {
        Write-Output 'PREPARED_NOT_STARTED. Use -Preflight before the first explicit -Run.'
        return
    }
    $existing = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('ANSYS.exe','mpiexec.exe','hydra_pmi_proxy.exe') })
    if ($existing.Count) { throw 'An ANSYS/MPI calculation already exists; no second process was started.' }
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connect = $client.BeginConnect('localhost', 1055, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(3000)) { throw 'Local license server localhost:1055 unavailable.' }
        $client.EndConnect($connect)
    } finally { $client.Close() }
    $env:ANSYSLMD_LICENSE_FILE = '1055@localhost'
    $env:ANS_USER_PATH = $root
    $env:ANS_USER_PATH_261 = $root
    $env:ANS_USE_UPF = ''

    if ($Preflight) {
        if (Select-String -Path 'preflight_v0.inp' -Pattern '^\s*SOLVE\b' -Quiet) { throw 'Unsafe preflight input.' }
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $log = Join-Path $root "preflight_$stamp.out"
        $proc = Start-Process -FilePath $ansys -WorkingDirectory $root -ArgumentList @('-b','-smp','-np','1','-p','ansys','-j',"preflight_$stamp",'-i',(Join-Path $root 'preflight_v0.inp'),'-o',$log) -PassThru -Wait
        if ($proc.ExitCode -ne 0) { throw "MAPDL preflight failed with code $($proc.ExitCode); see $log" }
        $text = Get-Content -Raw $log
        if ($text -notmatch 'V0_PREFLIGHT_COMPLETE_NO_SOLVE' -or $text -notmatch 'NODES=\s*229665' -or $text -notmatch 'ELEMENTS=\s*152000') {
            throw "Unexpected native preflight inventory; see $log"
        }
        $manifestHash = (Get-FileHash 'input_manifest.json' -Algorithm SHA256).Hash.ToLower()
        [System.IO.File]::WriteAllText((Join-Path $root 'PREFLIGHT_OK.txt'), "UTC=$([DateTime]::UtcNow.ToString('o'))`r`nLOG=$log`r`nMANIFEST_SHA256=$manifestHash`r`n")
        Write-Output "PREFLIGHT_OK_NO_SOLVE log=$log"
        return
    }

    if (-not (Test-Path 'PREFLIGHT_OK.txt')) { throw 'Run -Preflight before -Run.' }
    $preflightText = Get-Content -Raw 'PREFLIGHT_OK.txt'
    $manifestHash = (Get-FileHash 'input_manifest.json' -Algorithm SHA256).Hash.ToLower()
    if ($preflightText -notmatch "MANIFEST_SHA256=$manifestHash") { throw 'Inputs changed after native preflight; use a fresh runtime directory.' }
    if ($Resume) {
        $state = Get-Content -Raw 'state.json' | ConvertFrom-Json
        if ($state.status -ne 'PAUSED_AT_CHECKPOINT' -or $state.index -lt 1) { throw 'Resume is allowed only from an accepted paused checkpoint.' }
        if (Test-Path 'coupler_error.txt') { throw 'A coupling failure is present; automatic resume is blocked.' }
        if (Test-Path 'PAUSE_REQUESTED') { Remove-Item -LiteralPath 'PAUSE_REQUESTED' }
        $input = 'resume_v0.inp'
    } else {
        if ((Test-Path 'state.json') -or @(Get-ChildItem -File -Filter 'file.*').Count) {
            throw 'Existing run files are preserved. Use a new sibling runtime folder or resume a clean pause.'
        }
        & $python -B coupler.py initialize --root $root
        if ($LASTEXITCODE -ne 0) { throw 'Initialization failed.' }
        $input = 'run_v0.inp'
    }
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $log = Join-Path $root "solve_$stamp.out"
    Write-Output "Explicit launch: $input; ranks=$($cfg.ranks); local license; log=$log"
    $proc = Start-Process -FilePath $ansys -WorkingDirectory $root -ArgumentList @('-b','-dis','-np',[string]$cfg.ranks,'-p','ansys','-j','file','-i',(Join-Path $root $input),'-o',$log) -PassThru -Wait
    if ($proc.ExitCode -ne 0) { throw "MAPDL exited with $($proc.ExitCode); results were preserved; inspect $log." }
    Get-Content -Raw 'state.json' | ConvertFrom-Json | Select-Object index,time_s,status,layer
} finally {
    Pop-Location
}

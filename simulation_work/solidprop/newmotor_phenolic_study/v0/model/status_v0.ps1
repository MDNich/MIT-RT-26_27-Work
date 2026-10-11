$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$processes = Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('ANSYS.exe','mpiexec.exe','hydra_pmi_proxy.exe') }
$statePath = Join-Path $root 'state.json'
[pscustomobject]@{
    TimestampUtc = [DateTime]::UtcNow.ToString('o')
    AnsysProcesses = @($processes | Where-Object Name -eq 'ANSYS.exe').Count
    MpiExecProcesses = @($processes | Where-Object Name -eq 'mpiexec.exe').Count
    HydraProcesses = @($processes | Where-Object Name -eq 'hydra_pmi_proxy.exe').Count
    State = if (Test-Path $statePath) { Get-Content -Raw $statePath | ConvertFrom-Json } else { $null }
    LatestLog = Get-ChildItem -Path $root -Filter 'solve_*.out' -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 FullName,Length,LastWriteTime
} | ConvertTo-Json -Depth 8


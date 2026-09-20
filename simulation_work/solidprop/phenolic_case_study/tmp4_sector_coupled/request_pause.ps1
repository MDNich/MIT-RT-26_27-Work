$ErrorActionPreference='Stop'
$root=$PSScriptRoot
if (-not (Test-Path (Join-Path $root 'state.json'))) { throw 'Simulation not started.' }
[System.IO.File]::WriteAllText((Join-Path $root 'PAUSE_REQUESTED'),[DateTime]::UtcNow.ToString('o'))
Write-Output 'Pause requested at the next accepted macro-step. Do not kill ANSYS or suspend Windows.'

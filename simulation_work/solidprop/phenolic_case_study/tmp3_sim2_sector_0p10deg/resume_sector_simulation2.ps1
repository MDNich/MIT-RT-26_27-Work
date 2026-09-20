$ErrorActionPreference = "Stop"
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class NativeSectorResume {
  [DllImport("ntdll.dll", SetLastError=true)]
  public static extern uint NtResumeProcess(IntPtr processHandle);
}
"@

$records = Get-Content -LiteralPath "C:\ansys_sector_sim2\paused_processes.json" -Raw | ConvertFrom-Json
if (-not $records) { throw "Aucun manifeste de pause" }
foreach ($item in ($records | Sort-Object @{Expression={ if ($_.Name -eq "mpiexec.exe") {0} elseif ($_.Name -eq "ANSYS.exe") {1} else {2} }})) {
    $process = Get-Process -Id $item.ProcessId -ErrorAction Stop
    $code = [NativeSectorResume]::NtResumeProcess($process.Handle)
    if ($code -ne 0) { throw "NtResumeProcess a echoue pour PID $($item.ProcessId): $code" }
}
"RUNNING_UTC=$([DateTime]::UtcNow.ToString('o')) COUNT=$($records.Count)" |
    Out-File -LiteralPath "C:\ansys_sector_sim2\pause_state.txt" -Encoding utf8

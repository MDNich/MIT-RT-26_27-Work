$ErrorActionPreference = "Stop"
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class NativeSectorPause {
  [DllImport("ntdll.dll", SetLastError=true)]
  public static extern uint NtSuspendProcess(IntPtr processHandle);
}
"@

$targets = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -in @("ANSYS.exe", "mpiexec.exe", "hydra_pmi_proxy.exe") }
if (-not $targets) { throw "Aucun processus MAPDL/MPI actif" }

$records = @()
# Suspend workers first and the MPI/ANSYS parents last.
foreach ($item in ($targets | Sort-Object @{Expression={ if ($_.Name -eq "hydra_pmi_proxy.exe") {0} elseif ($_.Name -eq "ANSYS.exe") {1} else {2} }})) {
    $process = Get-Process -Id $item.ProcessId -ErrorAction Stop
    $code = [NativeSectorPause]::NtSuspendProcess($process.Handle)
    if ($code -ne 0) { throw "NtSuspendProcess a echoue pour PID $($item.ProcessId): $code" }
    $records += [pscustomobject]@{ Name=$item.Name; ProcessId=$item.ProcessId; CommandLine=$item.CommandLine }
}
$records | ConvertTo-Json -Depth 3 | Out-File -LiteralPath "C:\ansys_sector_sim2\paused_processes.json" -Encoding utf8
"PAUSED_UTC=$([DateTime]::UtcNow.ToString('o')) COUNT=$($records.Count)" |
    Out-File -LiteralPath "C:\ansys_sector_sim2\pause_state.txt" -Encoding utf8

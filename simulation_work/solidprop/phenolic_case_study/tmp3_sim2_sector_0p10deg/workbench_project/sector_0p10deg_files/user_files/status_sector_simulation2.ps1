$ErrorActionPreference = "Stop"
$processes = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -in @("ANSYS.exe", "mpiexec.exe", "hydra_pmi_proxy.exe") } |
    Select-Object Name, ProcessId, ParentProcessId, CreationDate, CommandLine
$processes | Format-Table Name,ProcessId,ParentProcessId,CreationDate -AutoSize
"PROCESS_COUNT=$($processes.Count)"
if (Test-Path "C:\ansys_sector_sim2\pause_state.txt") { Get-Content "C:\ansys_sector_sim2\pause_state.txt" }
$history = Get-ChildItem -Path "C:\ansys_sector_sim2\testbed2_files" -Filter simulation2_history.csv -Recurse -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($history) {
    "HISTORY=$($history.FullName)"
    Get-Content -LiteralPath $history.FullName -Tail 3
}
$output = Get-ChildItem -Path "C:\ansys_sector_sim2\testbed2_files" -Filter solve.out -Recurse -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($output) {
    "SOLVE_OUT=$($output.FullName)"
    Get-Content -LiteralPath $output.FullName -Tail 25
}

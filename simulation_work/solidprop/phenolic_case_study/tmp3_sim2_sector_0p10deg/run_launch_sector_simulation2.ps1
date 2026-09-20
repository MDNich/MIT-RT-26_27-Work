$ErrorActionPreference = "Stop"
$env:ANSYSLMD_LICENSE_FILE = "1055@localhost"
$env:ANS_USE_UPF = ""
$env:ANS_USER_PATH = "C:\ansys_sector_sim2"
$env:ANS_USER_PATH_261 = "C:\ansys_sector_sim2"
$workbench = "C:\Program Files\ANSYS Inc\v261\Framework\bin\Win64\RunWB2.exe"
$project = "C:\ansys_sector_sim2\testbed2.wbpj"
$journal = "C:\ansys_sector_sim2\launch_sector_simulation2.wbjn"
$result = "C:\ansys_sector_sim2\launch_sector_result.txt"

Remove-Item -LiteralPath $result -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process |
    Where-Object { $_.Name -in @("ANSYS.exe", "mpiexec.exe", "hydra_pmi_proxy.exe") } |
    Select-Object Name, ProcessId, CommandLine |
    ConvertTo-Json -Depth 3 |
    Out-File -LiteralPath "C:\ansys_sector_sim2\processes_before_launch.json" -Encoding utf8

$process = Start-Process -FilePath $workbench -ArgumentList @("-B", "-F", $project, "-R", $journal) -PassThru -Wait
"ExitCode=$($process.ExitCode)" | Out-File -FilePath $result -Encoding utf8
exit $process.ExitCode

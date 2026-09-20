$ErrorActionPreference = "Stop"
$env:ANSYSLMD_LICENSE_FILE = "1055@localhost"
$workbench = "C:\Program Files\ANSYS Inc\v261\Framework\bin\Win64\RunWB2.exe"
$project = "C:\ansys_sector_sim2\testbed2.wbpj"
$journal = "C:\ansys_sector_sim2\configure_sector_simulation2.wbjn"
$result = "C:\ansys_sector_sim2\configure_sector_result.txt"
Remove-Item -LiteralPath $result -Force -ErrorAction SilentlyContinue
$process = Start-Process -FilePath $workbench -ArgumentList @("-B", "-F", $project, "-R", $journal) -PassThru -Wait
"ExitCode=$($process.ExitCode)" | Out-File -FilePath $result -Encoding utf8
exit $process.ExitCode

$ErrorActionPreference = "Stop"
$env:ANSYSLMD_LICENSE_FILE = "1055@localhost"
$workbench = "C:\Program Files\ANSYS Inc\v261\Framework\bin\Win64\RunWB2.exe"
$journal = "C:\ansys_sector_sim2\unarchive_validate_sector.wbjn"
$process = Start-Process -FilePath $workbench -ArgumentList @("-B", "-R", $journal) -PassThru -Wait
"ExitCode=$($process.ExitCode)" | Out-File -FilePath "C:\ansys_sector_sim2\unarchive_validate_result.txt" -Encoding utf8
exit $process.ExitCode

$ErrorActionPreference = "Stop"
$root = "C:\ansys_sector_sim2"
$runwb = "C:\Program Files\ANSYS Inc\v261\Framework\bin\Win64\RunWB2.exe"
& $runwb -B -F "$root\testbed2.wbpj" -R "$root\import_and_archive_local.wbjn"
$exitCode = $LASTEXITCODE
Set-Content -LiteralPath "$root\import_and_archive_local.exitcode.txt" -Value $exitCode
exit $exitCode

$ErrorActionPreference = "Stop"
$root = "Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\solidprop\phenolic_case_study\tmp3_sim2_sector_0p10deg"
$runwb = "C:\Program Files\ANSYS Inc\v261\Framework\bin\Win64\RunWB2.exe"
& $runwb -B -F "$root\testbed2.wbpj" -R "$root\import_sector_geometry.wbjn"
$exitCode = $LASTEXITCODE
Set-Content -LiteralPath "$root\import_sector_geometry.exitcode.txt" -Value $exitCode
exit $exitCode

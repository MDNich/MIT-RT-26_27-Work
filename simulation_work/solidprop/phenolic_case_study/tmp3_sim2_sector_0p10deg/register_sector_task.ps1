$ErrorActionPreference = "Stop"
$xml = Get-Content -LiteralPath "C:\ansys_sector_sim2\CodexSectorSim2.xml" -Raw
Register-ScheduledTask -TaskName "CodexSectorSim2" -Xml $xml -Force | Out-Null
Start-ScheduledTask -TaskName "CodexSectorSim2"

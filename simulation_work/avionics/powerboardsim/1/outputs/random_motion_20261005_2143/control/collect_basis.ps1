$ErrorActionPreference='Stop'
$dest='\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis'
Copy-Item 'C:\Temp\PBMotion_20261005_basis\solve.out','C:\Temp\PBMotion_20261005_basis\file*.err' $dest
Get-ChildItem 'C:\Temp\PBMotion_20261005_basis' -File | Select-Object Name,Length,LastWriteTimeUtc | ConvertTo-Csv -NoTypeInformation | Out-File "$dest\runtime_inventory.csv"

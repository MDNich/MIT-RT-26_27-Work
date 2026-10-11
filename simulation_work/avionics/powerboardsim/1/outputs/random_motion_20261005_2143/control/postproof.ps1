$ErrorActionPreference='Stop'
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'PrepPost seat busy'}
$rt='C:\Temp\PBMotion_20261005_postproof'
New-Item -ItemType Directory -Path $rt -ErrorAction Stop | Out-Null
Copy-Item 'C:\Temp\PBMotion_20261005_basis_smp\file.db' $rt
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_vibration_20261005_0950\modal_basis\file.rst' "$rt\modes.rst"
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\postproof\run.dat' $rt
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j file -i run.dat -o run.out' -WorkingDirectory $rt -PassThru -Wait
Copy-Item "$rt\run.out","$rt\file.err" '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\postproof'
Get-ChildItem $rt -File | Select-Object Name,Length | ConvertTo-Csv -NoTypeInformation | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\postproof\inventory.csv'

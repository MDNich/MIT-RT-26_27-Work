$ErrorActionPreference='Stop'
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'PrepPost seat busy'}
New-Item -ItemType Directory -Path 'C:\Temp\PBMotion_20261005_transient_Y' -ErrorAction Stop | Out-Null
Get-ChildItem 'C:\Temp\PBMotion_20261005_basis_smp' -File | Where-Object { $_.Name -match '^file\.(db|mode|full|mlv|enf)$' } | Copy-Item -Destination 'C:\Temp\PBMotion_20261005_transient_Y'
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\transient_Y\run.dat','\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\transient_Y\preflight.dat' 'C:\Temp\PBMotion_20261005_transient_Y'
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\inputs\Y_acc.txt' 'C:\Temp\PBMotion_20261005_transient_Y\acc.txt'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j file -i preflight.dat -o preflight.out' -WorkingDirectory 'C:\Temp\PBMotion_20261005_transient_Y' -PassThru -Wait
Copy-Item 'C:\Temp\PBMotion_20261005_transient_Y\preflight.out','C:\Temp\PBMotion_20261005_transient_Y\file.err' '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\transient_Y'
$p.ExitCode | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\transient_Y\preflight_exit.txt'

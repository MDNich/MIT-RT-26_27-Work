$ErrorActionPreference='Stop'
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f ansys -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'Structural seat busy'}
New-Item -ItemType Directory -Path 'C:\Temp\PBMotion_20261005_stress_X_saved2' -ErrorAction Stop | Out-Null
Get-ChildItem 'C:\Temp\PBMotion_20261005_basis_saved' -File | Where-Object { $_.Name -match '^file\d*\.(db|mode|full|mlv|enf)$' } | Copy-Item -Destination 'C:\Temp\PBMotion_20261005_stress_X_saved2'
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\stress_X_saved2\run.dat','\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\stress_X_saved2\preflight.dat' 'C:\Temp\PBMotion_20261005_stress_X_saved2'
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\inputs\X_acc.txt' 'C:\Temp\PBMotion_20261005_stress_X_saved2\acc.txt'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p ansys -j file -i preflight.dat -o preflight.out' -WorkingDirectory 'C:\Temp\PBMotion_20261005_stress_X_saved2' -PassThru -Wait
Copy-Item 'C:\Temp\PBMotion_20261005_stress_X_saved2\preflight.out','C:\Temp\PBMotion_20261005_stress_X_saved2\file.err' '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\stress_X_saved2'
$p.ExitCode | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\stress_X_saved2\preflight_exit.txt'

Copy-Item 'C:\Temp\PBMotion_20261005_stress_X_saved2\basis_frequencies.csv' '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\stress_X_saved2'

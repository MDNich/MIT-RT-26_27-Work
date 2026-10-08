$ErrorActionPreference='Stop'
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver already active'}
New-Item -ItemType Directory -Path 'C:\Temp\PBMotion_20261005_pilot_X_32768' -ErrorAction Stop | Out-Null
Get-ChildItem 'C:\Temp\PBMotion_20261005_basis' -File | Where-Object { $_.Name -match '^file\d*\.(db|mode|full|mlv|enf)$' } | Copy-Item -Destination 'C:\Temp\PBMotion_20261005_pilot_X_32768'
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\pilot_X_32768\run.dat','\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\pilot_X_32768\preflight.dat' 'C:\Temp\PBMotion_20261005_pilot_X_32768'
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\inputs\X_acc.txt' 'C:\Temp\PBMotion_20261005_pilot_X_32768\acc.txt'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j check -i preflight.dat -o preflight.out' -WorkingDirectory 'C:\Temp\PBMotion_20261005_pilot_X_32768' -PassThru -Wait
Copy-Item 'C:\Temp\PBMotion_20261005_pilot_X_32768\preflight.out','C:\Temp\PBMotion_20261005_pilot_X_32768\check.err' '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\pilot_X_32768'
$p.ExitCode | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\pilot_X_32768\preflight_exit.txt'

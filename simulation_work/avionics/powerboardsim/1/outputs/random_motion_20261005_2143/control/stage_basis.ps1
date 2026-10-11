$ErrorActionPreference='Stop'
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver already active'}
New-Item -ItemType Directory -Path 'C:\Temp\PBMotion_20261005_basis' -ErrorAction Stop | Out-Null
Get-ChildItem '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\powerboardsim_v1_files\dp0\SYS-4\MECH' -File | Where-Object { $_.Name -match '^file\d*\.(db|mode|full|esav|emat)$' -or $_.Name -eq 'file.DSP' } | Copy-Item -Destination 'C:\Temp\PBMotion_20261005_basis'
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis\run.dat','\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis\preflight.dat' 'C:\Temp\PBMotion_20261005_basis'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j check -i preflight.dat -o preflight.out' -WorkingDirectory 'C:\Temp\PBMotion_20261005_basis' -PassThru -Wait
Copy-Item 'C:\Temp\PBMotion_20261005_basis\preflight.out','C:\Temp\PBMotion_20261005_basis\check.err' '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis'
$p.ExitCode | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis\preflight_exit.txt'

$ErrorActionPreference='Stop'
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'PrepPost seat busy'}
New-Item -ItemType Directory -Path 'C:\Temp\PBMotion_20261005_pilot_expand_dmp' -ErrorAction Stop | Out-Null
Get-ChildItem 'C:\Temp\PBMotion_20261005_pilot_X_32768' -File | Where-Object {$_.Name -match '^file\d*\.(db|mode|full|mlv|enf|rdsp)$'} | Copy-Item -Destination 'C:\Temp\PBMotion_20261005_pilot_expand_dmp'
Get-ChildItem 'C:\Temp\PBMotion_20261005_basis' -File | Where-Object {$_.Name -match '^file\d*\.(emat|esav)$'} | Copy-Item -Destination 'C:\Temp\PBMotion_20261005_pilot_expand_dmp'
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\pilot_expand_dmp\run.dat','\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\pilot_expand_dmp\preflight.dat' 'C:\Temp\PBMotion_20261005_pilot_expand_dmp'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j file -i preflight.dat -o preflight.out' -WorkingDirectory 'C:\Temp\PBMotion_20261005_pilot_expand_dmp' -PassThru -Wait
Copy-Item 'C:\Temp\PBMotion_20261005_pilot_expand_dmp\preflight.out','C:\Temp\PBMotion_20261005_pilot_expand_dmp\file.err' '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\pilot_expand_dmp'
$p.ExitCode | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\pilot_expand_dmp\preflight_exit.txt'

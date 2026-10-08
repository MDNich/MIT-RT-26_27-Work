$ErrorActionPreference='Stop'
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f ansys -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'Structural seat busy'}
New-Item -ItemType Directory -Path 'C:\Temp\PBMotion_20261005_expand_Z' -ErrorAction Stop | Out-Null
if(Test-Path 'C:\Temp\PBMotion_20261005_expand_Y\file.lock'){throw 'Y still active'}
if(!(Test-Path '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\expand_Y\COLLECTED.txt')){throw 'Y not archived'}
foreach($ext in @('mode','full','mlv','emat','esav')){Move-Item ('C:\Temp\PBMotion_20261005_expand_Y\file.'+$ext) 'C:\Temp\PBMotion_20261005_expand_Z'}
Copy-Item 'C:\Temp\PBMotion_20261005_transient_Z\file.db','C:\Temp\PBMotion_20261005_transient_Z\file.rdsp' 'C:\Temp\PBMotion_20261005_expand_Z'
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\expand_Z\run.dat','\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\expand_Z\preflight.dat' 'C:\Temp\PBMotion_20261005_expand_Z'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p ansys -j file -i preflight.dat -o preflight.out' -WorkingDirectory 'C:\Temp\PBMotion_20261005_expand_Z' -PassThru -Wait
Copy-Item 'C:\Temp\PBMotion_20261005_expand_Z\preflight.out','C:\Temp\PBMotion_20261005_expand_Z\file.err' '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\expand_Z'
$p.ExitCode | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\expand_Z\preflight_exit.txt'

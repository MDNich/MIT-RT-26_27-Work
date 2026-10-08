$ErrorActionPreference='Stop'
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver active'}
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f ansys -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'Seat busy'}
$rt='C:\Temp\PBMotion_20261005_dpf_global_stress_check'
New-Item -ItemType Directory -Path $rt -ErrorAction Stop | Out-Null
$cache='C:\Temp\PBMotion_20261005_stress_lcproof_v3'
Copy-Item "$cache\file.db" $rt
New-Item -ItemType HardLink -Path "$rt\modes.rst" -Target "$cache\modes.rst" | Out-Null
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\dpf_global_stress_check\run.dat' $rt
if((Get-FileHash "$rt\run.dat").Hash.ToLower() -ne 'ca59536232ce3df6eeabf898875bb90e3ebb3e5e44e1ccca3904b663af271b83'){throw 'Input mismatch'}
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p ansys -j file -i run.dat -o run.out' -WorkingDirectory $rt -PassThru -Wait
foreach($n in @('run.out','file.err','modal_nodes.csv')){if(Test-Path "$rt\$n"){Copy-Item "$rt\$n" '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\dpf_global_stress_check'}}
$p.ExitCode | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\dpf_global_stress_check\exit_code.txt'

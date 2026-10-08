$ErrorActionPreference='Stop'
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver already active'}
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f ansys -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'Structural seat busy'}
$rt='C:\Temp\PBMotion_20261005_stress_lcproof_v3'
New-Item -ItemType Directory -Path $rt -ErrorAction Stop | Out-Null
$src='C:\Temp\PCBRV_20261005_X_local\file.rst'
if((Get-FileHash $src).Hash.ToLower() -ne 'd25a334f3d1dc2e2f0921390624357f5e9bbb55d6281376ab194d8fdb6163c03'){throw 'Source mode result mismatch'}
New-Item -ItemType HardLink -Path "$rt\modes.rst" -Target $src | Out-Null
New-Item -ItemType HardLink -Path "$rt\seed.rst" -Target 'C:\Temp\PBMotion_20261005_expand_X\file.rst' | Out-Null
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_vibration_20261005_0950\modal_basis\file.db' "$rt\file.db"
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\stress_lcproof_v3\run.dat' $rt
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p ansys -j file -i run.dat -o run.out' -WorkingDirectory $rt -PassThru -Wait
Copy-Item "$rt\run.out","$rt\file.err","$rt\modal_nodes.csv","$rt\combined_nodes.csv" '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\stress_lcproof_v3'
$p.ExitCode | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\stress_lcproof_v3\exit_code.txt'

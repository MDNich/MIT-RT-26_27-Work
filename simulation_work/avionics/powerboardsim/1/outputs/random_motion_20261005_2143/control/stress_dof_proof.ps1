$ErrorActionPreference='Stop'
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver active'}
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f ansys -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'Seat busy'}
$rt='C:\Temp\PBMotion_20261005_stress_dof_proof'
New-Item -ItemType Directory -Path $rt -ErrorAction Stop | Out-Null
$cache='C:\Temp\PBMotion_20261005_stress_lcproof_v3'
Copy-Item "$cache\file.db" $rt
foreach($n in @('modes.rst','seed.rst')){New-Item -ItemType HardLink -Path "$rt\$n" -Target "$cache\$n" | Out-Null}
$files=@(Get-ChildItem "$cache\shape*.lcs");if($files.Count -ne 38){throw 'Missing modal cache'}
foreach($f in $files){New-Item -ItemType HardLink -Path "$rt\$($f.Name)" -Target $f.FullName | Out-Null}
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\stress_dof_proof\run.dat' $rt
if((Get-FileHash "$rt\run.dat").Hash.ToLower() -ne '3200bff3723a590651e8b4942056a5172c75a896c30e036cdfd9a7ad49ff7bf9'){throw 'Input mismatch'}
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p ansys -j file -i run.dat -o run.out' -WorkingDirectory $rt -PassThru -Wait
foreach($n in @('run.out','file.err','combined_nodes.csv','roundtrip_nodes.csv','displacement_nodes.csv')){if(Test-Path "$rt\$n"){Copy-Item "$rt\$n" '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\stress_dof_proof'}}
$p.ExitCode | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\stress_dof_proof\exit_code.txt'

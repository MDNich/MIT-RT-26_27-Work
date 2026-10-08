$ErrorActionPreference='Stop'
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'PrepPost seat busy'}
$rt='C:\Temp\PBMotion_20261005_basis_aux_smp'
New-Item -ItemType Directory -Path $rt -ErrorAction Stop | Out-Null
Get-ChildItem 'C:\Temp\PBMotion_20261005_basis' -File | Where-Object {$_.Name -match '^file\d+\.(emat|esav)$'} | Copy-Item -Destination $rt
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis_aux_smp\combine.dat' $rt
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -s noread -dis -np 12 -p preppost -j file -i combine.dat -o combine.out' -WorkingDirectory $rt -PassThru -Wait
Copy-Item "$rt\combine.out","$rt\file*.err" '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis_aux_smp'
$p.ExitCode | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis_aux_smp\exit_code.txt'
Get-ChildItem $rt -File | Select-Object Name,Length | ConvertTo-Csv -NoTypeInformation | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis_aux_smp\inventory.csv'

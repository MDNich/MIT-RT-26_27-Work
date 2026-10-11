$ErrorActionPreference='Stop'
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver already active'}
New-Item -ItemType Directory -Path 'C:\Temp\PBMotion_20261005_basis_saved' -ErrorAction Stop | Out-Null
if(Test-Path 'C:\Temp\PCBRV_20261005_X_local\file.lock'){throw 'Old failed runtime is locked'}
$original=Get-Content '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis_saved\source_files.json' -Raw | ConvertFrom-Json
foreach($f in $original){$p='C:\Temp\PCBRV_20261005_X_local\'+$f.name;if((Get-FileHash $p).Hash.ToLower() -ne $f.sha256){throw ('Source hash mismatch '+$f.name)}}
foreach($f in $original){Move-Item ('C:\Temp\PCBRV_20261005_X_local\'+$f.name) 'C:\Temp\PBMotion_20261005_basis_saved'}
Copy-Item '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis_saved\run.dat','\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis_saved\preflight.dat' 'C:\Temp\PBMotion_20261005_basis_saved'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p ansys -j file -i preflight.dat -o preflight.out' -WorkingDirectory 'C:\Temp\PBMotion_20261005_basis_saved' -PassThru -Wait
Copy-Item 'C:\Temp\PBMotion_20261005_basis_saved\preflight.out','C:\Temp\PBMotion_20261005_basis_saved\file.err' '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis_saved'
$p.ExitCode | Out-File '\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\basis_saved\preflight_exit.txt'

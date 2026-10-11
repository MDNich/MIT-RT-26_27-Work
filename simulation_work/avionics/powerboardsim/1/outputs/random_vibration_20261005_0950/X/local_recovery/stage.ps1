
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver process exists'}
New-Item -ItemType Directory -Path 'C:\Temp\PCBRV_20261005_X_local' -ErrorAction Stop | Out-Null
Get-ChildItem 'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\powerboardsim_v1_files\dp0\SYS-4\MECH' -File | Where-Object { $_.Name -match '^file\d*\.(db|mode|full|esav|emat|rst)$' -or $_.Name -eq 'file.DSP' } | Copy-Item -Destination 'C:\Temp\PCBRV_20261005_X_local'
Copy-Item 'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_vibration_20261005_0950\X\local_recovery\run.dat','Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_vibration_20261005_0950\X\local_recovery\preflight.dat' 'C:\Temp\PCBRV_20261005_X_local'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j psdcheck -i preflight.dat -o preflight.out' -WorkingDirectory 'C:\Temp\PCBRV_20261005_X_local' -PassThru -Wait
Copy-Item 'C:\Temp\PCBRV_20261005_X_local\preflight.out','C:\Temp\PCBRV_20261005_X_local\psdcheck.err','C:\Temp\PCBRV_20261005_X_local\excitation_nodes.txt' 'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_vibration_20261005_0950\X\local_recovery'
Write-Output ('Local preflight exit '+$p.ExitCode)

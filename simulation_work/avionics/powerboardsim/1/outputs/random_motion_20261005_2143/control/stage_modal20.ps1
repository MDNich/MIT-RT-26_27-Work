$ErrorActionPreference='Stop'
$out='C:\Temp\PBMotion_modal20'
New-Item -ItemType Directory -Path $out -ErrorAction Stop | Out-Null
Copy-Item 'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\bolt_manager_work\resume_20261005_004228\bolted750_modal\file.rst' "$out\file.rst"
if((Get-FileHash "$out\file.rst").Hash.ToLower() -ne '812cacda84f169b54920ccb8b971210523df45b4aa0cad17feaac050b8a8ed9d'){throw 'Modal source hash mismatch'}
'VERIFIED'

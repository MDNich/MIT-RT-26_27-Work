$ErrorActionPreference='Stop'
$out='\\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143\expand_X'
Copy-Item C:\Temp\PBMotion_20261005_expand_X\file.rst,C:\Temp\PBMotion_20261005_expand_X\solve.out,C:\Temp\PBMotion_20261005_expand_X\file.err $out
(Get-FileHash ($out+'\file.rst')).Hash | Out-File ($out+'\rst.sha256')
'done' | Set-Content ($out+'\COLLECTED.txt')

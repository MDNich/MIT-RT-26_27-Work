$ErrorActionPreference='Stop'
$p=Get-Process -Id 15208
if($p.ProcessName -ne 'AnsysWBU' -or $p.Responding){throw 'Unexpected state'}
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver active'}
Stop-Process -Id 15208 -Force

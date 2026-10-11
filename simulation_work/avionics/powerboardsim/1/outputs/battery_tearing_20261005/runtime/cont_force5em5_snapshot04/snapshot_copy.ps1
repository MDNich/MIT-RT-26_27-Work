
$ErrorActionPreference='Stop'
$src='C:\Temp\PBTear26_cont_force5em5'
$dst='C:\Temp\PBTear26_cont_force5em5_snapshot04'
if(Test-Path $dst){throw 'Native snapshot destination already exists'}
if(-not (Test-Path "$src\tear.lock")){throw 'Source not running: inspect completion and use normal postprocessing'}
New-Item -ItemType Directory -Path $dst -ErrorAction Stop | Out-Null
$before=Get-Item "$src\tear.rst"
$bytes=$before.Length
$ticks=$before.LastWriteTimeUtc.Ticks
$modelHash=(Get-FileHash "$src\model.db").Hash
Copy-Item "$src\tear.rst","$src\model.db" $dst
$after=Get-Item "$src\tear.rst"
$copy=Get-Item "$dst\tear.rst"
$copiedModelHash=(Get-FileHash "$dst\model.db").Hash
$stable=($bytes -eq $after.Length -and $ticks -eq $after.LastWriteTimeUtc.Ticks -and $bytes -eq $copy.Length -and $modelHash -eq $copiedModelHash)
Copy-Item "$src\run.out","$src\tear.err" $dst
$record=@{source=$src;destination=$dst;utc=(Get-Date).ToUniversalTime().ToString('o');rst_length_before=$bytes;rst_length_after=$after.Length;rst_length_copy=$copy.Length;rst_ticks_before=$ticks;rst_ticks_after=$after.LastWriteTimeUtc.Ticks;model_sha256=$copiedModelHash.ToLower();stable_during_copy=$stable;source_solver_active=(Test-Path "$src\tear.lock")}
$record | ConvertTo-Json | Set-Content "$dst\NATIVE_SNAPSHOT.json" -Encoding UTF8
Copy-Item "$dst\NATIVE_SNAPSHOT.json" 'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\battery_tearing_20261005\runtime\cont_force5em5_snapshot04'
if(-not $stable){throw 'Snapshot changed during copy; evidence preserved, do not postprocess'}
$record | ConvertTo-Json

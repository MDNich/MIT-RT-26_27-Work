$ErrorActionPreference='Stop'
$src='C:\Temp\PBTear26_cont_fine'
$dst='C:\Temp\PBTear26_cont_fine_snapshot01'
if(Test-Path $dst){throw 'Native snapshot exists'}
if(-not (Test-Path "$src\tear.lock")){throw 'Source not running; inspect completion instead'}
if((Get-FileHash "$src\run.dat").Hash.ToLower() -ne '3a346d134b99dae3c72729e765f433fc76d8350b1b14e2ae39dc49b4f37aedd3'){throw 'Source input changed'}
New-Item -ItemType Directory -Path $dst -ErrorAction Stop | Out-Null
$before=Get-Item "$src\tear.rst"
$bytes=$before.Length
$ticks=$before.LastWriteTimeUtc.Ticks
$modelHash=(Get-FileHash "$src\model.db").Hash
Copy-Item "$src\tear.rst","$src\model.db","$src\run.dat" $dst
$after=Get-Item "$src\tear.rst"
$copy=Get-Item "$dst\tear.rst"
$copiedModelHash=(Get-FileHash "$dst\model.db").Hash
$stable=($bytes -eq $after.Length -and $ticks -eq $after.LastWriteTimeUtc.Ticks -and $bytes -eq $copy.Length -and $modelHash -eq $copiedModelHash)
Copy-Item "$src\run.out","$src\tear.err","$src\solve_progress.csv" $dst
$record=@{source=$src;destination=$dst;utc=(Get-Date).ToUniversalTime().ToString('o');rst_length_before=$bytes;rst_length_after=$after.Length;rst_length_copy=$copy.Length;rst_ticks_before=$ticks;rst_ticks_after=$after.LastWriteTimeUtc.Ticks;rst_copy_ticks=$copy.LastWriteTimeUtc.Ticks;model_sha256=$copiedModelHash.ToLower();stable_during_copy=$stable;source_solver_active=(Test-Path "$src\tear.lock")}
$record | ConvertTo-Json | Set-Content "$dst\NATIVE_SNAPSHOT.json" -Encoding UTF8
if(-not $stable){throw 'Unstable copy; preserve evidence and do not postprocess'}
$record | ConvertTo-Json

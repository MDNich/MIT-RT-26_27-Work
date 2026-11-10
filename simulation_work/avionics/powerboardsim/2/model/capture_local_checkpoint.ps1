# Copy the active forward pull without issuing a solver command. The destination
# is the study's Mac-backed checkpoint directory, accessible through Parallels.
$ErrorActionPreference='Stop'
$name='snug125_nylon_lateral_friction_locked_pin1_m15'
$w='C:\Temp\PBCaseStudy\nov08_01\'+$name
$base=Join-Path (Split-Path $PSScriptRoot) '.runtime\qa\snug125\forward-readback'
if (-not (Test-Path $base -PathType Container)) { throw 'Checkpoint root missing' }
$p=$w+'\pull.rst';$mon=$w+'\pull.mntr';$before=Get-Content $mon -Tail 1
$col=$before.Trim() -split '\s+';$key='ls'+$col[0]+'_ss'+$col[1]
$dir=Join-Path $base $key
if(Test-Path $dir){throw 'Existing substep snapshot or staging directory'}
New-Item -ItemType Directory -Path $dir|Out-Null
$stamp=(Get-Item $p).LastWriteTimeUtc.Ticks
$src=[IO.File]::Open($p,'Open','Read','ReadWrite')
try {
  $size=$src.Length
  $copy=[IO.File]::Open((Join-Path $dir 'pull.rst.incoming'),'CreateNew','Write','None')
  try {$src.CopyTo($copy,1048576)} finally {$copy.Dispose()}
  $src.Position=0;$hash=[Security.Cryptography.SHA256]::Create()
  try {$sum=[BitConverter]::ToString($hash.ComputeHash($src)).Replace('-','').ToLower()} finally {$hash.Dispose()}
  if($size -ne $src.Length){throw 'RST length changed during snapshot'}
}finally{$src.Dispose()}
Copy-Item -LiteralPath $mon -Destination (Join-Path $dir 'pull.mntr')
Copy-Item -LiteralPath ($w+'\solve.out') -Destination (Join-Path $dir 'solve.out')
if($before -ne (Get-Content $mon -Tail 1) -or $stamp -ne (Get-Item $p).LastWriteTimeUtc.Ticks){throw 'Result or step changed during snapshot'}
Move-Item (Join-Path $dir 'pull.rst.incoming') (Join-Path $dir 'pull.rst')
@{case=$name;campaign='nov08_01';source=$p;sha256=$sum;bytes=$size;last_monitor=[string]$before;source_mtime_ticks=$stamp;captured_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $dir 'capture.json') -Encoding UTF8
Write-Output $key

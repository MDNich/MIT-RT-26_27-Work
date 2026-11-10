# Read one stationary result prefix from an ongoing primary local pull.
param([ValidatePattern('^snug125_(nylon|aluminium)_lateral_friction_locked(_minus)?_pin1_m15$')]
      [string]$Case='snug125_nylon_lateral_friction_locked_pin1_m15')
$ErrorActionPreference='Stop'
$name=$Case
$root=Split-Path $PSScriptRoot
$w=Join-Path 'C:\Temp\PBCaseStudy\nov08_01' $name
$receipt=Join-Path $root ".runtime\receipts\nov08_01\$name\status.json"
if (!(Test-Path -LiteralPath $receipt -PathType Leaf)) {throw 'The requested pull has no matching live case receipt'}
$status=Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
$spec=(Get-Content -LiteralPath "$root\validation\snug125\local_inputs_m15.json" -Raw | ConvertFrom-Json).PSObject.Properties[$name].Value
if ($null -eq $spec -or $status.case -ne $name -or $status.phase -ne 'solving' -or
    $status.work -ne $w -or $status.input_sha256 -ne $spec.input_sha256) {throw 'The requested pull has no matching live case receipt'}
$qa=Join-Path $root '.runtime\qa\snug125'
$base=if ($name -eq 'snug125_nylon_lateral_friction_locked_pin1_m15') {Join-Path $qa 'forward-readback'} else {Join-Path $qa "directional-readback\$name"}
New-Item -ItemType Directory -Path $base -Force | Out-Null
$p=$w+'\pull.rst';$mon=$w+'\pull.mntr';$before=Get-Content $mon -Tail 1
$col=$before.Trim() -split '\s+';$key='ls'+$col[0]+'_ss'+$col[1]
if ($col.Count -lt 9 -or $col[0] -ne '3' -or $col[1] -notmatch '^[1-9][0-9]*$') {throw 'No completed lateral increment in the monitor'}
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

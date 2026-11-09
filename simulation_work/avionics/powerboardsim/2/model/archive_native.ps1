param([Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_]+$')][string]$Case,
      [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_]+$')][string]$Campaign)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$root=Split-Path $PSScriptRoot
$work=Join-Path "C:\Temp\PBCaseStudy\$Campaign" $Case
$receipt=Join-Path $root ".runtime\receipts\$Campaign\$Case"
$dst=Join-Path $root ".runtime\archive\$Campaign\$Case"
if ((Get-Content "$receipt\status.json" -Raw |ConvertFrom-Json).phase -ne 'solver_complete') {throw 'Solver completion record required'}
New-Item -ItemType Directory -Path $dst -Force|Out-Null
$finish="$receipt\archived.json"
try {
if (Test-Path $finish) {
    $ledger=@((Get-Content $finish -Raw|ConvertFrom-Json).files)
} else {
$ledger=@()
$files=Get-ChildItem $work -File
foreach ($file in $files) {
    $copy=Join-Path $dst $file.Name
    $expected=(Get-FileHash -LiteralPath $file.FullName).Hash.ToLower()
    if (!(Test-Path -LiteralPath $copy)){
        $temp="$copy.incoming"
        Copy-Item -LiteralPath $file.FullName -Destination $temp -Force
        if ((Get-FileHash -LiteralPath $temp).Hash -ne $expected){throw "Archive copy differs: $($file.Name)"}
        Move-Item -LiteralPath $temp -Destination $copy
    } elseif ((Get-FileHash -LiteralPath $copy).Hash -ne $expected){throw "Existing archive differs: $($file.Name)"}
    $ledger+=[PSCustomObject]@{name=$file.Name;bytes=$file.Length;sha256=$expected}
}
if (!($ledger|Where-Object name -eq 'file.rst')){throw 'Missing assembled result file'}
$manifest=[ordered]@{case=$Case;campaign=$Campaign;source=$work;utc=[datetime]::UtcNow.ToString('o');files=$ledger}
$manifest|ConvertTo-Json -Depth 5|Set-Content "$finish.tmp" -Encoding UTF8
Move-Item "$finish.tmp" $finish
}
# Files at the completed fresh guest path now have verified SHA-256 host copies.
# Keep the deck, logs and small control files for diagnosis, release large duplicate outputs.
foreach ($row in $ledger | Where-Object bytes -gt 5000000) {
  $src=Join-Path $work $row.name
  if (!(Test-Path -LiteralPath $src)){continue}
  if ((Get-FileHash -LiteralPath (Join-Path $dst $row.name)).Hash -ne $row.sha256){throw 'Archive hash changed before guest cleanup'}
  if ((Get-FileHash -LiteralPath $src).Hash -ne $row.sha256){throw 'Closed file changed after archiving'}
  Remove-Item -LiteralPath $src
}
'Guest large-file cleanup complete'|Set-Content "$receipt\released.txt"
} catch {
    $_.Exception.Message|Set-Content "$receipt\archive_error.txt"
    throw
}

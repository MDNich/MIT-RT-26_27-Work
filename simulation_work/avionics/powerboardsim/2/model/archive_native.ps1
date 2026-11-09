param([Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_]+$')][string]$Case,
      [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_]+$')][string]$Campaign,[switch]$Stopped)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$root=Split-Path $PSScriptRoot
$work=Join-Path "C:\Temp\PBCaseStudy\$Campaign" $Case
$receipt=Join-Path $root ".runtime\receipts\$Campaign\$Case"
$dst=Join-Path $root ".runtime\archive\$Campaign\$Case"
$status=Get-Content "$receipt\status.json" -Raw|ConvertFrom-Json
if ($status.shared_scratch) {
    $expected=Join-Path $root ".runtime\shared_native\$Campaign\$Case"
    if ($status.local_guard -ne $work -or $expected -ne $status.work -or $status.case -ne $Case){throw 'Unexpected shared archive source'}
    $work=$expected
}
$manifestName='archived.json';$releaseName='released.txt'
if ($Stopped) {
    if ($status.phase -ne 'failed' -or $status.case -ne $Case -or $status.work -ne $work -or $status.failure -notmatch 'scratch reserve|Insufficient space for a fresh structural job') {throw 'Expected a closed scratch-stop receipt'}
    foreach ($sample in 1,2) {
        $active=@(Get-CimInstance Win32_Process -ErrorAction Stop|Where-Object { $_.Name -match '^(ANSYS(261)?|mapdl|mpiexec|hydra_pmi_proxy)\.exe$' -or ($_.Name -eq 'powershell.exe' -and $_.CommandLine -like "*\native_run.ps1 -Case $Case -Campaign $Campaign*") })
        if ($active.Count){throw 'Guest solver or runner is still active'}
        if ($sample -eq 1){Start-Sleep -Seconds 3}
    }
    $dst=Join-Path $root ".runtime\stopped_archive\$Campaign\$Case"
    $manifestName='stopped_archived.json';$releaseName='stopped_released.txt'
} elseif ($status.phase -ne 'solver_complete') {throw 'Solver completion record required'}
New-Item -ItemType Directory -Path $dst -Force|Out-Null
$finish=Join-Path $receipt $manifestName
$lease=[System.IO.File]::Open("$receipt\archive.lock",[System.IO.FileMode]::OpenOrCreate,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::None)
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
$result=if ($status.motion_kind -eq 'transient'){'file.mcf'}elseif($status.motion_kind -eq 'enforced'){'file.full'}elseif ($status.result_job -in 'pull','tear'){ $status.result_job+'.rst' }else{ 'file.rst' }
if ($Stopped) {
    $inputFile=@($ledger|Where-Object name -eq 'model.inp')
    if ($inputFile.Count -ne 1 -or $inputFile[0].sha256 -ne $status.input_sha256){throw 'Stopped source input identity failed'}
} elseif (!($ledger|Where-Object name -eq $result)){throw 'Missing assembled result file'}
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
'Guest large-file cleanup complete'|Set-Content (Join-Path $receipt $releaseName)
} catch {
    $_.Exception.Message|Set-Content "$receipt\archive_error.txt"
    throw
} finally {$lease.Dispose()}

param([Parameter(Mandatory)][string]$Work,[Parameter(Mandatory)][string]$Case,
      [Parameter(Mandatory)][string]$Campaign,[Parameter(Mandatory)][string]$Exe)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$spec=Get-Content -LiteralPath "$Work\motion_job.json" -Raw|ConvertFrom-Json
if ($spec.case -ne $Case -or $spec.campaign -ne $Campaign -or $spec.kind -notin 'enforced','transient'){throw 'Invalid motion job identity'}
$root=Split-Path $PSScriptRoot
$basis=Get-Content -LiteralPath "$root\validation\global\$($spec.branch)_basis.json" -Raw|ConvertFrom-Json
if ($basis.rst_sha256 -ne $spec.basis_rst_sha256 -or $basis.frequencies_Hz.Count -ne $spec.modes){throw 'Changed parent basis'}
foreach ($row in $spec.files.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath "$Work\$($row.Name)").Hash -ne $row.Value){throw "Motion deck hash mismatch: $($row.Name)"}
}
function Run-Deck([string]$Mode,[string]$Cores,[string]$Deck,[string]$Listing) {
    $p=Start-Process -FilePath $Exe -WorkingDirectory $Work -ArgumentList @('-b','nolist','-s','noread',$Mode,'-np',$Cores,'-p','ansys','-j','file','-i',$Deck,'-o',$Listing) -Wait -PassThru
    if ($p.ExitCode -ne 0 -or !(Select-String -LiteralPath "$Work\$Listing" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)) {throw "$Deck failed"}
}
if ($spec.kind -eq 'enforced') {
    Run-Deck '-dis' '12' 'model.inp' 'solve.out'
    if (!(Select-String -LiteralPath "$Work\solve.out" -Pattern 'NUMBER OF STATIC SHAPES\s*=\s*3\b' -Quiet)){throw 'Missing enforced motion shapes'}
    Run-Deck '-dis' '12' 'combine.inp' 'combine.out'
} else {
    if ((Get-FileHash -LiteralPath "$Work\acc.txt").Hash -ne $spec.acc_sha256){throw 'Acceleration checksum mismatch'}
    foreach ($name in 'file.db','file.mode','file.full','file.mlv'){
        if (!(Test-Path -LiteralPath "$Work\$name")){throw "Missing single-process parent $name"}
    }
    Run-Deck '-smp' '1' 'model.inp' 'solve.out'
}

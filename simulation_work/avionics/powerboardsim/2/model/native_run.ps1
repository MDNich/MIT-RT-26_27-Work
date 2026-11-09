param([Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9_]+$')][string]$Case,[Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_]+$')][string]$Campaign,[int]$Cores=12,[string]$Parent='')
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$share=Split-Path $PSScriptRoot
$inputDir=Join-Path $share ".runtime\inputs\$Case"
if (!(Test-Path -LiteralPath "$inputDir\model.inp") -and $Case -match '^(?:flush|stand3)_(?:nylon|aluminium)_(modal20|basis|psd_[XYZ])$'){
    $inputDir=Join-Path $share ('.runtime\inputs\bare_'+$Matches[1])
}
$out=Join-Path $share ".runtime\receipts\$Campaign\$Case"
$base=Join-Path 'C:\Temp\PBCaseStudy' $Campaign
$work=Join-Path $base $Case
$exe='C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
$env:ANSYSLMD_LICENSE_FILE='1055@localhost'
if (!(Test-Path -LiteralPath $exe)){throw "Missing solver $exe"}
if (Test-Path -LiteralPath $work){throw "Preserving existing job $work"}
$active=@(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(ANSYS\d+|mapdl|mpiexec|hydra_pmi_proxy)$' })
if ($active.Count){throw "Another native job is running"}
New-Item -ItemType Directory -Path $work -Force|Out-Null
New-Item -ItemType Directory -Path $out -Force|Out-Null
$stage=[ordered]@{case=$Case;work=$work;utc=[DateTime]::UtcNow.ToString('o');phase='staging';cores=$Cores}
function Update([string]$Phase){$stage.phase=$Phase;$stage.updated=[DateTime]::UtcNow.ToString('o');$stage|ConvertTo-Json|Set-Content -LiteralPath "$out\status.tmp" -Encoding UTF8;Move-Item "$out\status.tmp" "$out\status.json" -Force}
try {
    Update 'staging'
    Get-ChildItem -LiteralPath $inputDir -File | Copy-Item -Destination $work
    $stage.input_sha256=(Get-FileHash "$work\model.inp").Hash
    if ($stage.input_sha256 -ne (Get-FileHash "$inputDir\model.inp").Hash){throw 'Staging checksum failed'}
    if ((Get-PSDrive C).Free -lt 18000000000){throw 'Insufficient space for a fresh structural job'}
    if ($Parent) {
        if ($Parent -notmatch '^[A-Za-z0-9_]+$') {throw 'Invalid parent'}
        $parentRoot=Join-Path $share ".runtime\archive\$Campaign\$Parent"
        $parentReceipt=Join-Path $share ".runtime\receipts\$Campaign\$Parent\archived.json"
        $manifest=Get-Content $parentReceipt -Raw|ConvertFrom-Json
        $pattern=if($Case -match '_psd_'){'^file(?:[0-9]*)\.(?:db|mode|full|esav|emat|rst|dsp)$'}else{'^file(?:[0-9]*)\.(?:rdb|ldhi|r[0-9]{3,}|rst|dsp|emat|esav|full|db|rsm|rth|s[0-9]{2,})$'}
        $parents=@($manifest.files|Where-Object name -match $pattern)
        if ($parents.Count -lt 3) {throw 'Parent restart files missing'}
        $needed=($parents|Measure-Object bytes -Sum).Sum
        if ((Get-PSDrive C).Free -lt $needed+9000000000){throw "Insufficient space for parent and solver scratch"}
        $stage.parent=$Parent
        foreach($row in $parents){
            $to=Join-Path $work $row.name
            Copy-Item -LiteralPath (Join-Path $parentRoot $row.name) -Destination $to
            if((Get-FileHash -LiteralPath $to).Hash -ne $row.sha256){throw "Parent copy mismatch: $($row.name)"}
        }
    }
    Update 'solving'
    $argsList=@('-b','nolist','-s','noread','-dis','-np',"$Cores",'-p','ansys','-j','file','-i','model.inp','-o','solve.out')
    $p=Start-Process -FilePath $exe -WorkingDirectory $work -ArgumentList $argsList -Wait -PassThru
    $stage.exit=$p.ExitCode
    Copy-Item "$work\solve.out" $out
    Get-ChildItem $work -Filter '*.err' | Copy-Item -Destination $out
    if ($p.ExitCode -ne 0 -or !(Select-String -Path "$work\solve.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)){throw 'Native solve failed. Inspect solve.out.'}
    Update 'solver_complete'
} catch {$stage.failure=$_.Exception.Message;Update 'failed';throw}

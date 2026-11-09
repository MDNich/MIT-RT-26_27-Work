param([Parameter(Mandatory)][string]$Work,
      [Parameter(Mandatory)][string]$Case,[Parameter(Mandatory)][string]$Exe)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$spec=Get-Content -LiteralPath "$Work\local_job.json" -Raw|ConvertFrom-Json
if ($spec.case -ne $Case -or $spec.job -notin 'tear','pull' -or $spec.cores -notin 1,4){throw 'Invalid local fixture specification'}
$published=Get-Content -LiteralPath "$PSScriptRoot\..\validation\local_jobs.json" -Raw|ConvertFrom-Json
$record=$published.PSObject.Properties[$Case].Value
if ((Get-FileHash -LiteralPath "$Work\local_job.json").Hash -ne $record.spec_sha256){throw 'Local specification identity failed'}
foreach ($item in $spec.files.PSObject.Properties){
    if ((Get-FileHash -LiteralPath (Join-Path $Work $item.Name)).Hash -ne $item.Value){throw "Staging checksum failed: $($item.Name)"}
}
$job=$spec.job
$native=Start-Process -FilePath $Exe -WorkingDirectory $Work -Wait -PassThru -ArgumentList @(
    '-b','nolist','-s','noread','-smp','-np',"$($spec.cores)",'-p','ansys','-j',$job,'-i','model.inp','-o','solve.out')
$listing="$Work\solve.out"
$clean=($native.ExitCode -eq 0) -and (Select-String -LiteralPath $listing -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)
if (!(Test-Path -LiteralPath "$Work\$job.rst")){throw 'No local result file'}
if (!$clean -and !(Select-String -LiteralPath $listing -Pattern 'LOAD STEP\s+\d+\s+SUBSTEP\s+\d+\s+COMPLETED' -Quiet)){
    throw 'Local solve failed before its first equilibrium state'
}
if (!$spec.coupon) {
    foreach ($stem in 'moving','local_post'){
        $p=Start-Process -FilePath $Exe -WorkingDirectory $Work -Wait -PassThru -ArgumentList @(
            '-b','nolist','-s','noread','-smp','-np','1','-p','preppost','-j',$stem,'-i',"$stem.inp",'-o',"$stem.out")
        if ($p.ExitCode -ne 0 -or !(Select-String -LiteralPath "$Work\$stem.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)){
            throw "Local $stem result readback failed"
        }
    }
}
[PSCustomObject]@{exit=$native.ExitCode;clean=$clean;job=$job;cores=$spec.cores}

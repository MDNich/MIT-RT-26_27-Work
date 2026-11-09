param([Parameter(Mandatory)][string]$Work,
      [Parameter(Mandatory)][string]$Case,[Parameter(Mandatory)][string]$Exe,[Parameter(Mandatory)][string]$Receipt)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$spec=Get-Content -LiteralPath "$Work\local_job.json" -Raw|ConvertFrom-Json
if ($spec.case -ne $Case -or $spec.job -notin 'tear','pull' -or $spec.cores -notin 1,4){throw 'Invalid local fixture specification'}
$catalog=if ($Case.EndsWith('_seatfaces1')) {'local_seat_jobs.json'} elseif ($Case.EndsWith('_approach1')) {'local_install_jobs.json'} elseif ($Case.EndsWith('_pin1')) {'local_contact_retries.json'} else {'local_jobs.json'}
if ($Case.EndsWith('_seatfaces1') -and $spec.nominal_geometry_source) { $catalog='flush_pull_variants.json' }
if ($spec.case_template -and $spec.source -like 'lateral_grip_*') { $catalog='perfect_grip_cases.json' }
$published=Get-Content -LiteralPath "$PSScriptRoot\..\validation\$catalog" -Raw|ConvertFrom-Json
$record=$published.PSObject.Properties[$Case].Value
if ((Get-FileHash -LiteralPath "$Work\local_job.json").Hash -ne $record.spec_sha256){throw 'Local specification identity failed'}
foreach ($item in $spec.files.PSObject.Properties){
    if ((Get-FileHash -LiteralPath (Join-Path $Work $item.Name)).Hash -ne $item.Value){throw "Staging checksum failed: $($item.Name)"}
}
$job=$spec.job
$arguments=@('-b','nolist','-s','noread','-smp','-np',"$($spec.cores)",'-p','ansys','-j',$job,'-i','model.inp','-o','solve.out')
if ($spec.load_protocol -in 'four_stage_install','grip_install' -and (Get-PSDrive C).Free -lt 24000000000) {
    throw 'Insufficient guest headroom for installation path'
}
$native=Start-Process -FilePath $Exe -WorkingDirectory $Work -PassThru -ArgumentList $arguments
Wait-NativeProcess $native $Work $job $Receipt $false
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

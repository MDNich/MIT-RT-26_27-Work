param([Parameter(Mandatory)][string]$Work,
      [Parameter(Mandatory)][string]$Case,[Parameter(Mandatory)][string]$Exe,[Parameter(Mandatory)][string]$Receipt)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$spec=Get-Content -LiteralPath "$Work\local_job.json" -Raw|ConvertFrom-Json
if ($spec.case -ne $Case -or $spec.job -notin 'tear','pull' -or $spec.cores -notin 1,4){throw 'Invalid local fixture specification'}
$catalog=if ($Case.EndsWith('_seatfaces1')) {'local_seat_jobs.json'} elseif ($Case.EndsWith('_approach1')) {'local_install_jobs.json'} elseif ($Case.EndsWith('_pin1')) {'local_contact_retries.json'} else {'local_jobs.json'}
if ($Case.EndsWith('_seatfaces1') -and $spec.nominal_geometry_source) { $catalog='flush_pull_variants.json' }
if ($Case -eq 'flush_nylon_lateral_friction_locked_rock1_seatfaces1') { $catalog='rocking_bearing_input.json' }
if ($spec.case_template -and $spec.source -like 'lateral_grip_*') { $catalog='perfect_grip_cases.json' }
if ($spec.sensitivity_reference) { $catalog='damage_variant_inputs.json' }
if ($spec.common_load_parent) { $catalog='common_pull_resolution.json' }
if ($spec.detection_parent) { $catalog='pull_detection_control.json' }
if ($Case.StartsWith('snug125_')) {
    $catalog=if ($spec.snug_sensitivity) { 'snug125/local_sensitivity_inputs.json' } else { 'snug125/local_inputs.json' }
}
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
# A failed coupon solve can exit before its inline POST1 commands. Read the closed
# RST in a new process and skip the unbalanced diagnostic set in every coupon.
if ($spec.coupon) {
    $postInput=Join-Path $PSScriptRoot 'coupon_post.inp'
    $postProof=Get-Content -LiteralPath "$PSScriptRoot\..\validation\coupon_reference\october.json" -Raw|ConvertFrom-Json
    $destination=Join-Path $Work 'coupon_post.inp'
    Copy-Item -LiteralPath $postInput -Destination $destination
    if ((Get-FileHash -LiteralPath $destination).Hash -ne $postProof.post_input_sha256){throw 'Coupon readback input identity failed'}
    $readbacks=@('coupon_post')
} else {
    $readbacks=@('moving','local_post')
}
foreach ($stem in $readbacks){
    $p=Start-Process -FilePath $Exe -WorkingDirectory $Work -Wait -PassThru -ArgumentList @(
        '-b','nolist','-s','noread','-smp','-np','1','-p','preppost','-j',$stem,'-i',"$stem.inp",'-o',"$stem.out")
    if ($p.ExitCode -ne 0 -or !(Select-String -LiteralPath "$Work\$stem.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)){
        throw "Local $stem result readback failed"
    }
}
[PSCustomObject]@{exit=$native.ExitCode;clean=$clean;job=$job;cores=$spec.cores}

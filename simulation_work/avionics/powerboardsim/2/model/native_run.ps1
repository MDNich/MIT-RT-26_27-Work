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
# The November 10 forward pull loaded the old readback wrapper. Reconcile its observed
# nonconvergence at this serial boundary before starting a different structural solve.
$oldCase='snug125_nylon_lateral_friction_locked_pin1_m15'
$oldReceipt=Join-Path $share ".runtime\receipts\$Campaign\$oldCase"
if ($Campaign -eq 'nov08_01' -and $Case -ne $oldCase -and (Test-Path "$oldReceipt\observed_solver_exit.json") -and
    !(Test-Path "$oldReceipt\released.txt") -and !(Test-Path "$oldReceipt\recovery_error.txt")) {
    try {
        & "$PSScriptRoot\recover_observed_pull.ps1" -Campaign $Campaign
        if (Test-Path "$oldReceipt\closed_post_recovery.json") {
            & "$PSScriptRoot\archive_native.ps1" -Case $oldCase -Campaign $Campaign
        }
    } catch {
        $_.Exception.Message|Set-Content "$oldReceipt\recovery_error.txt" -Encoding UTF8
    }
}
$active=@(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(ANSYS|ANSYS\d+|mapdl|mpiexec|hydra_pmi_proxy)$' })
if ($active.Count){throw "Another native job is running"}
New-Item -ItemType Directory -Path $work -ErrorAction Stop|Out-Null
$guard=$work
$enforcedMotion = $Case -match '^(?:bare|(?:stand3|snug125)_(?:nylon|aluminium)|flush_(?:nylon|aluminium)_surf1)_enforced$'
$sharedWork=(Test-Path -LiteralPath "$share\validation\shared_dmp_control.json") -and ($enforcedMotion -or $Case -match '^(?:(?:stand3_aluminium|stand3_nylon_mesh2|snug125_(?:nylon|aluminium)|snug125_(?:nylon|aluminium)_mesh15|snug125_nylon_mesh3)_basis|flush_(?:nylon|aluminium)_(?:surf1_(?:static|basis|modal20)|default_(?:original|refined)_(?:static|modal20)))$')
if ($sharedWork) {
    $work=Join-Path $share ".runtime\shared_native\$Campaign\$Case"
    if (Test-Path -LiteralPath $work){throw 'Preserving the existing shared working directory'}
}
New-Item -ItemType Directory -Path $out -Force|Out-Null
$stage=[ordered]@{case=$Case;work=$work;utc=[DateTime]::UtcNow.ToString('o');phase='staging';cores=$Cores}
function Update([string]$Phase){$stage.phase=$Phase;$stage.updated=[DateTime]::UtcNow.ToString('o');$stage|ConvertTo-Json|Set-Content -LiteralPath "$out\status.tmp" -Encoding UTF8;Move-Item "$out\status.tmp" "$out\status.json" -Force}
try {
    . "$PSScriptRoot\wait_native.ps1"
    Update 'staging'
    if ($sharedWork) {
        $control=Get-Content "$share\validation\shared_dmp_control.json" -Raw|ConvertFrom-Json
        if ($control.ranks -ne $Cores -or $control.trial -ne 'shared_dmp_io_v1'){throw 'Shared scratch DMP control mismatch'}
        New-Item -ItemType Directory -Path $work -Force|Out-Null
        $stage.local_guard=$guard
        $stage.shared_scratch=$true
    }
    Get-ChildItem -LiteralPath $inputDir -File | Copy-Item -Destination $work
    $stage.input_sha256=(Get-FileHash "$work\model.inp").Hash
    $history=Join-Path $share 'validation\storage_recovery.json'
    if (Test-Path -LiteralPath $history) {
        $old=(Get-Content -LiteralPath $history -Raw|ConvertFrom-Json).PSObject.Properties[$Case]
        if ($old -and $old.Value.campaign -eq $Campaign) {
            $previous="$share\.runtime\stopped_receipts\$Campaign\$Case\stopped_archived.json"
            if ((Get-FileHash -LiteralPath $previous).Hash -ne $old.Value.original_manifest_sha256 -or
                $stage.input_sha256 -ne $old.Value.sealed_input_sha256){throw 'Recovered case input or original evidence mismatch'}
            $stage.previous_storage_attempt_sha256=$old.Value.original_manifest_sha256
        }
    }
    if ($Case -match '^snug125_(nylon|aluminium)_original_sturm$') {
        $entry=Get-Content "$share\validation\${Case}_input.json" -Raw | ConvertFrom-Json
        $core=Get-Content "$share\validation\snug125\global_inputs.json" -Raw | ConvertFrom-Json
        if ($entry.retry -ne $Case -or $entry.campaign -ne $Campaign -or $entry.retry_input_sha256 -ne $stage.input_sha256 -or
            $core.PSObject.Properties[$entry.source].Value.input_sha256 -ne $entry.original_input_sha256 -or $Parent) {throw 'Snug default-mesh retry lineage mismatch'}
    }
    if ($Case -match '^snug125_(?:nylon|aluminium)_mesh15_basis$') {
        if ($Case -eq 'snug125_aluminium_mesh15_basis') {
            $series=Get-Content "$share\validation\snug125\aluminium_refinement_inputs.json" -Raw | ConvertFrom-Json
            $entry=$series.PSObject.Properties[$Case].Value
        } else {
            $entry=Get-Content "$share\validation\snug125\modal_refinement_input.json" -Raw | ConvertFrom-Json
            $series=Get-Content "$share\validation\snug125\contact_refinement_inputs.json" -Raw | ConvertFrom-Json
        }
        $fine=$series.PSObject.Properties[$Parent].Value
        if ($entry.case -ne $Case -or $entry.parent -ne $Parent -or $entry.input_sha256 -ne $stage.input_sha256 -or
            $entry.parent_input_sha256 -ne $fine.input_sha256 -or $entry.mesh_sha256 -ne $fine.mesh_sha256 -or
            $entry.step_sha256 -ne $fine.step_sha256 -or $entry.size_mm -ne 1.5 -or $entry.tab_spacing_mm -ne 1.25) {
            throw 'Fine prestressed basis or parent mesh identity mismatch'
        }
    }
    $forceReadback = $Case -match '^snug125_(?:nylon_(?:out2|mesh15|tol001|mesh15_tol001)|aluminium_(?:mesh15|out2|project3|cylinder|tol001))_static$'
    if ($forceReadback) {
        $book=Get-Content "$share\validation\snug125\contact_refinement_inputs.json" -Raw | ConvertFrom-Json
        if ($Case -eq 'snug125_aluminium_mesh15_static') {
            $al=Get-Content "$share\validation\snug125\aluminium_refinement_inputs.json" -Raw | ConvertFrom-Json
            $entry=$al.PSObject.Properties[$Case].Value
            $nylon=$book.PSObject.Properties['snug125_nylon_mesh15_static'].Value
            if ($entry.case -ne $Case -or $entry.material -ne 'aluminium' -or $entry.nylon_fine_input_sha256 -ne $nylon.input_sha256 -or
                $entry.mesh_sha256 -ne $nylon.mesh_sha256 -or $entry.post_sha256 -ne $nylon.post_sha256) {throw 'Fine aluminium control lineage mismatch'}
        } elseif ($Case -eq 'snug125_aluminium_out2_static') {
            $entry=Get-Content "$share\validation\snug125\aluminium_force_repeat_input.json" -Raw | ConvertFrom-Json
            $main=Get-Content "$share\validation\snug125\global_inputs.json" -Raw | ConvertFrom-Json
            $ref=$main.PSObject.Properties['snug125_aluminium_static'].Value
            if ($entry.case -ne $Case -or $entry.reference_case -ne 'snug125_aluminium_static' -or
                $entry.reference_input_sha256 -ne $ref.input_sha256 -or $entry.mesh_sha256 -ne $ref.mesh_sha256 -or
                $entry.post_sha256 -ne $book.PSObject.Properties['snug125_nylon_out2_static'].Value.post_sha256) {throw 'Nominal aluminium force lineage mismatch'}
        } elseif ($Case -eq 'snug125_aluminium_project3_static') {
            $entry=Get-Content "$share\validation\snug125\aluminium_projection_input.json" -Raw | ConvertFrom-Json
            $ref=Get-Content "$share\validation\snug125\aluminium_force_repeat_input.json" -Raw | ConvertFrom-Json
            if ($entry.case -ne $Case -or $entry.reference_case -ne $ref.case -or $entry.reference_input_sha256 -ne $ref.input_sha256 -or
                $entry.mesh_sha256 -ne $ref.mesh_sha256 -or $entry.post_sha256 -ne $ref.post_sha256 -or $entry.detection_keyopt_4 -ne 3) {throw 'Aluminium contact projection lineage mismatch'}
        } elseif ($Case -eq 'snug125_aluminium_cylinder_static') {
            $entry=Get-Content "$share\validation\snug125\aluminium_cylinder_input.json" -Raw | ConvertFrom-Json
            $ref=Get-Content "$share\validation\snug125\aluminium_force_repeat_input.json" -Raw | ConvertFrom-Json
            if ($entry.case -ne $Case -or $entry.reference_case -ne $ref.case -or $entry.reference_input_sha256 -ne $ref.input_sha256 -or
                $entry.mesh_sha256 -ne $ref.mesh_sha256 -or $entry.post_sha256 -ne $ref.post_sha256 -or $entry.groups.Count -ne 2 -or
                $entry.detection_keyopt_4 -ne 0) {throw 'Aluminium cylinder control lineage mismatch'}
        } elseif ($Case -like '*_tol001_static') {
            if ($Case -eq 'snug125_nylon_tol001_static') {
                $entry=Get-Content "$share\validation\snug125\force_tolerance_input.json" -Raw | ConvertFrom-Json
                $referenceCase='snug125_nylon_out2_static'
                $ref=$book.PSObject.Properties[$referenceCase].Value
            } else {
                $other=Get-Content "$share\validation\snug125\extra_force_tolerance_inputs.json" -Raw | ConvertFrom-Json
                $entry=$other.PSObject.Properties[$Case].Value
                if ($Case -eq 'snug125_aluminium_tol001_static') {
                    $referenceCase='snug125_aluminium_out2_static'
                    $ref=Get-Content "$share\validation\snug125\aluminium_force_repeat_input.json" -Raw | ConvertFrom-Json
                } else {
                    $referenceCase='snug125_nylon_mesh15_static'
                    $ref=$book.PSObject.Properties[$referenceCase].Value
                }
            }
            if ($entry.case -ne $Case -or $entry.reference_case -ne $referenceCase -or
                $entry.reference_input_sha256 -ne $ref.input_sha256 -or $entry.mesh_sha256 -ne $ref.mesh_sha256 -or
                $entry.post_sha256 -ne $ref.post_sha256 -or $entry.absolute_force_criterion_N -ne 0.01) {throw 'Snug force tolerance lineage mismatch'}
        } else {
            $entry=$book.PSObject.Properties[$Case].Value
        }
        if ($entry.input_sha256 -ne $stage.input_sha256 -or $entry.step_sha256 -ne '43016e8435a85fc9ad33346ae11c0051102591c85a1fcee5ddd5658f75ca98ef' -or
            $entry.post_sha256 -ne (Get-FileHash "$work\snug_force_post.inp").Hash -or $entry.tab_spacing_mm -ne 1.25 -or $Parent) {throw 'Snug contact refinement identity mismatch'}
    }
    if ($Case -eq 'snug125_nylon_mesh3_basis') {
        $entry=Get-Content "$share\validation\snug125\coarse_geometry_modes.json" -Raw | ConvertFrom-Json
        $book=Get-Content "$share\validation\snug125\global_inputs.json" -Raw | ConvertFrom-Json
        $coarse=$book.PSObject.Properties[$Parent].Value
        $nominal=$book.PSObject.Properties['snug125_nylon_basis'].Value
        $installed="$share\validation\snug125\snug125_nylon_mesh3_static_installed.json"
        if ($Parent -ne 'snug125_nylon_mesh3_static' -or $entry.parent -ne $Parent -or $entry.case -ne $Case -or
            $entry.input_sha256 -ne $stage.input_sha256 -or $entry.reference_input_sha256 -ne $nominal.input_sha256 -or
            $entry.parent_input_sha256 -ne $coarse.input_sha256 -or $entry.mesh_sha256 -ne $coarse.mesh_sha256 -or
            $entry.step_sha256 -ne $coarse.step_sha256 -or $entry.tab_spacing_mm -ne 1.25 -or $entry.size_mm -ne 3 -or
            (Get-FileHash -LiteralPath $installed).Hash -ne $entry.installed_sha256) {throw 'Coarse displacement basis or its locked parent differs from registry'}
    } elseif ($Case -match '^snug125_(nylon|aluminium)(_mesh3)?_(static|original|refined|modal20|basis)$') {
        $manifest=Get-Content "$share\validation\snug125\global_inputs.json" -Raw | ConvertFrom-Json
        $entry=$manifest.PSObject.Properties[$Case].Value
        if ($entry.step_sha256 -ne '43016e8435a85fc9ad33346ae11c0051102591c85a1fcee5ddd5658f75ca98ef' -or
            $entry.tab_spacing_mm -ne 1.25 -or $entry.input_sha256 -ne $stage.input_sha256 -or [string]$entry.parent -ne $Parent) {
            throw 'Snug Balius input identity or mounting position mismatch'
        }
    }
    if ($stage.input_sha256 -ne (Get-FileHash "$inputDir\model.inp").Hash){throw 'Staging checksum failed'}
    if ((Get-PSDrive C).Free -lt 18000000000){throw 'Insufficient space for a fresh structural job'}
    if ($Case -like '*_cellpush_x' -and !$Parent) {throw 'Whole-board cell load requires its installed parent'}
    if ($Parent) {
        if ($Parent -notmatch '^[A-Za-z0-9_]+$') {throw 'Invalid parent'}
        $parentRoot=Join-Path $share ".runtime\archive\$Campaign\$Parent"
        $parentReceipt=Join-Path $share ".runtime\receipts\$Campaign\$Parent\archived.json"
        $manifest=Get-Content $parentReceipt -Raw|ConvertFrom-Json
        if ($Case -match '^(bare|snug125_(?:nylon|aluminium))_cellpush_x$') {
            $expectedParent=$Matches[1]+'_static'
            $entry=(Get-Content "$share\validation\snug125\whole_board_pull_inputs.json" -Raw|ConvertFrom-Json).PSObject.Properties[$Case].Value
            $locked=Get-Content "$share\validation\global\$Parent.json" -Raw|ConvertFrom-Json
            if ($entry.case -ne $Case -or $entry.campaign -ne $Campaign -or $Parent -ne $expectedParent -or
                $entry.parent -ne $Parent -or $entry.input_sha256 -ne $stage.input_sha256 -or $Cores -ne 12 -or
                $entry.native_ranks -ne $Cores -or $entry.parent_rst_sha256 -ne $locked.rst_sha256 -or
                $manifest.case -ne $Parent -or $manifest.campaign -ne $Campaign -or
                (Get-FileHash -LiteralPath $parentReceipt).Hash -ne $entry.parent_ledger_sha256) {throw 'Whole-board cell loading lineage differs'}
        }
        $pattern=if($Case -match '_enforced$'){'^file(?:[0-9]*)\.(?:db|mode|full|esav|emat|dsp|mlv)$'}elseif($Case -match '_motion_[XYZ]$'){'^file\.(?:db|mode|full|enf|mlv)$'}elseif($Case -match '_psd_'){'^file(?:[0-9]*)\.(?:db|mode|full|esav|emat|rst|dsp)$'}else{'^file(?:[0-9]*)\.(?:rdb|ldhi|r[0-9]{3,}|rst|dsp|emat|esav|full|db|rsm|rth|s[0-9]{2,})$'}
        $parents=@($manifest.files|Where-Object name -match $pattern)
        if ($parents.Count -lt 3) {throw 'Parent restart files missing'}
        $needed=($parents|Measure-Object bytes -Sum).Sum
        if (!$sharedWork -and !(Test-Path -LiteralPath "$work\remote_psd.json") -and !(Test-Path -LiteralPath "$work\private_psd.json") -and (Get-PSDrive C).Free -lt $needed+14000000000){throw "Insufficient space for parent and solver scratch"}
        if (Test-Path -LiteralPath "$work\remote_psd.json"){
            $remote=Get-Content -LiteralPath "$work\remote_psd.json" -Raw|ConvertFrom-Json
            if ($Case -notmatch '^((?:stand3|flush)_(?:nylon|aluminium)(?:_surf1)?)_psd_[XYZ]$'){throw 'Invalid remote PSD case'}
            $branch=$Matches[1]
            $pub=Get-Content -LiteralPath "$share\validation\remote_psd_inputs\$branch.json" -Raw|ConvertFrom-Json
            $lib=Join-Path $share ".runtime\modal_library\$Campaign\$Parent"
            if ($remote.case -ne $Case -or $remote.campaign -ne $Campaign -or $remote.parent -ne $Parent -or $remote.modal_dir -ne $lib -or
                $stage.input_sha256 -ne $remote.input_sha256 -or (Get-FileHash "$work\remote_psd.json").Hash -ne $pub.cases.PSObject.Properties[$Case].Value.spec_sha256 -or
                (Get-FileHash "$lib.json").Hash -ne $remote.library_manifest_sha256){throw 'Remote PSD request identity failed'}
            $parents=@($manifest.files|Where-Object name -eq 'file.db')
            if ($parents.Count -ne 1 -or $parents[0].sha256 -ne $remote.parent_db_sha256){throw 'Wrong local seed database'}
            $stage.remote_psd=$true
        }
        if (Test-Path -LiteralPath "$work\private_psd.json"){
            $spec=Get-Content -LiteralPath "$work\private_psd.json" -Raw|ConvertFrom-Json
            $pub=Get-Content -LiteralPath "$share\validation\private_psd_inputs\$Case.json" -Raw|ConvertFrom-Json
            $lib=Join-Path $share ".runtime\private_modal\$Campaign\$Case"
            if ($spec.case -ne $Case -or $spec.campaign -ne $Campaign -or $spec.parent -ne $Parent -or
                $spec.modal_dir -ne $lib -or $stage.input_sha256 -ne $spec.input_sha256 -or
                (Get-FileHash "$work\private_psd.json").Hash -ne $pub.spec_sha256 -or
                (Get-FileHash "$share\.runtime\modal_library\$Campaign\$Parent.json").Hash -ne $spec.parent_manifest_sha256){
                throw 'Private modal-directory identity failed'
            }
            $probe=[System.IO.File]::Open("$lib\file0.mode",[System.IO.FileMode]::Open,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::ReadWrite)
            $probe.Dispose()
            $parents=@($manifest.files|Where-Object name -eq 'file.db')
            if ($parents.Count -ne 1 -or $parents[0].sha256 -ne $spec.parent_db_sha256){throw 'Wrong modal seed DB'}
            $stage.private_psd=$true
        }
        $stage.parent=$Parent
        foreach($row in $parents){
            $to=Join-Path $work $row.name
            Copy-Item -LiteralPath (Join-Path $parentRoot $row.name) -Destination $to
            if((Get-FileHash -LiteralPath $to).Hash -ne $row.sha256){throw "Parent copy mismatch: $($row.name)"}
        }
    }
    if (Test-Path -LiteralPath "$work\motion_job.json") {
        $spec=Get-Content "$work\motion_job.json" -Raw|ConvertFrom-Json
        $stage.motion_kind=$spec.kind
        $stage.cores=if ($spec.kind -eq 'transient') {1} else {12}
        Update 'solving'
        & "$PSScriptRoot\motion_solve.ps1" -Work $work -Case $Case -Campaign $Campaign -Exe $exe -SharedWork $sharedWork
        $stage.exit=0
        Copy-Item -LiteralPath "$work\solve.out" $out
        Update 'solver_complete'
        return
    }
    if (Test-Path -LiteralPath "$work\local_job.json") {
        $spec=Get-Content "$work\local_job.json" -Raw|ConvertFrom-Json
        . "$PSScriptRoot\local_runtime.ps1"
        $runtime=Get-LocalRuntime $spec $Case $Campaign $share
        if ($runtime.trial_sha256) {
            Copy-Item -LiteralPath "$share\validation\snug125\local_core_trial.json" -Destination "$out\local_core_trial.json"
            if ((Get-FileHash -LiteralPath "$out\local_core_trial.json").Hash -ne $runtime.trial_sha256) {
                $runtime.Remove('trial_sha256')
                $runtime.cores=[int]$spec.cores
                $runtime.fallback_reason='Timing receipt changed during launch preparation'
            }
        }
        $stage.cores=$runtime.cores
        $stage.local_runtime=$runtime
        Update 'solving'
        $localResult=& "$PSScriptRoot\local_solve.ps1" -Work $work -Case $Case -Exe $exe -Receipt $out -SolveCores $runtime.cores
        if ($localResult.cores -ne $stage.cores) {throw 'Local solver core count differs from its receipt'}
        $stage.exit=$localResult.exit
        $stage.native_clean=$localResult.clean
        $stage.result_job=$localResult.job
        Copy-Item -LiteralPath "$work\solve.out" $out
        Update 'solver_complete'
        return
    }
    if ($Case -match '^stand3_nylon_mesh2_(static|basis)$') {
        $ref=(Get-Content "$share\validation\case_refinement_inputs.json" -Raw|ConvertFrom-Json).cases.PSObject.Properties[$Case].Value
        if ($ref.input_sha256 -ne $stage.input_sha256 -or [string]$ref.parent -ne $Parent){throw 'Refined case input or parent mismatch'}
    }
    $surfaceJob=$null
    $isDefaultSeat=$Case -match '^flush_(nylon|aluminium)_default_(original|refined)_(static|modal20)$'
    if ($isDefaultSeat -or $Case -match '^flush_(nylon|aluminium)_surf1_(static|modal20|basis)$'){
        $surfaceJob=Get-Content -LiteralPath "$work\surface_job.json" -Raw|ConvertFrom-Json
        $registry=if($isDefaultSeat){'default_contact_jobs.json'}else{'board_surface_jobs.json'}
        $pub=(Get-Content "$share\validation\$registry" -Raw|ConvertFrom-Json).PSObject.Properties[$Case].Value
        if ($surfaceJob.case -ne $Case -or $stage.input_sha256 -ne $surfaceJob.model_sha256 -or
            (Get-FileHash "$work\surface_job.json").Hash -ne $pub.spec_sha256 -or [string]$surfaceJob.parent -ne $Parent){throw 'Wrong surface-contact job or parent'}
        if ($surfaceJob.kind -eq 'static' -and (Get-FileHash "$work\board_surface_post.inp").Hash -ne $surfaceJob.post_sha256){throw 'Wrong seating readback'}
    }
    Update 'solving'
    $argsList=@('-b','nolist','-s','noread','-dis','-np',"$Cores",'-p','ansys','-j','file','-i','model.inp','-o','solve.out')
    if ($Case -eq 'snug125_nylon_clamp_smp12'){
        $trial=Get-Content "$share\validation\snug125\local_core_trial_input.json" -Raw|ConvertFrom-Json
        $book=Get-Content "$share\validation\snug125\local_inputs_m15.json" -Raw|ConvertFrom-Json
        $row=$book.PSObject.Properties[$trial.parent].Value
        if ($Parent -or $Cores -ne 12 -or $trial.trial_cores -ne $Cores -or $trial.case -ne $Case -or
            $trial.input_sha256 -ne $stage.input_sha256 -or $trial.parent_spec_sha256 -ne $row.spec_sha256 -or
            $trial.parent_input_sha256 -ne $row.input_sha256 -or $trial.mesh_sha256 -ne $row.mesh_sha256){
            throw 'Local SMP clamp trial identity mismatch'
        }
        $argsList=@('-b','nolist','-s','noread','-smp','-np',"$Cores",'-p','ansys','-j','file','-i','model.inp','-o','solve.out')
    }
    if ($Case.StartsWith('shell_snug125_')){
        if ($Case -notmatch '^shell_(snug125_(?:nylon|aluminium))_(?:free|contact)_v2$'){throw 'Unknown whole-shell case'}
        $branch=$Matches[1]
        $pub=(Get-Content "$share\validation\snug125\${branch}_shell_inputs_v2.json" -Raw|ConvertFrom-Json).PSObject.Properties[$Case].Value
        if ($pub.case -ne $Case -or $pub.campaign -ne $Campaign -or $pub.spacing_mm -ne 1.25 -or $Cores -ne 2 -or
            $pub.step_sha256 -ne '43016e8435a85fc9ad33346ae11c0051102591c85a1fcee5ddd5658f75ca98ef'){
            throw 'Whole-shell fixture provenance mismatch'
        }
        foreach ($entry in $pub.files.PSObject.Properties){
            if ((Get-FileHash -LiteralPath (Join-Path $work $entry.Name)).Hash -ne $entry.Value){throw 'Whole-shell drive checksum failed'}
        }
        $argsList=@('-b','nolist','-s','noread','-smp','-np',"$Cores",'-p','ansys','-j','file','-i','model.inp','-o','solve.out')
    }
    if ($Case.StartsWith('shellwave_')){
        if ($Case -notmatch '^shellwave_(snug125_(?:nylon|aluminium))_(?:free|contact)_pilot_s4$'){throw 'Unknown whole-shell transient pilot'}
        $branch=$Matches[1]
        $registry="$share\validation\snug125\${branch}_shellwave_pilot_s4.json"
        $pre=Get-Content "$share\validation\snug125\${branch}_shellwave_pilot_s4_preflight.json" -Raw|ConvertFrom-Json
        $pub=(Get-Content $registry -Raw|ConvertFrom-Json).PSObject.Properties[$Case].Value
        if ($pre.registry_sha256 -ne (Get-FileHash $registry).Hash -or $pub.case -ne $Case -or $pub.campaign -ne $Campaign -or
            $pub.spacing_mm -ne 1.25 -or $pub.final_sample -ne 64 -or $Cores -ne 2 -or $Parent -or
            $pub.step_sha256 -ne '43016e8435a85fc9ad33346ae11c0051102591c85a1fcee5ddd5658f75ca98ef'){throw 'Transient pilot provenance mismatch'}
        foreach ($entry in $pub.files.PSObject.Properties){
            if ((Get-FileHash -LiteralPath (Join-Path $work $entry.Name)).Hash -ne $entry.Value){throw 'Transient pilot input checksum failed'}
        }
        $argsList=@('-b','nolist','-s','noread','-smp','-np',"$Cores",'-p','ansys','-j','file','-i','model.inp','-o','solve.out')
    }
    if ($Case.StartsWith('replay_')){
        $pub=(Get-Content "$share\validation\contact_replay_inputs.json" -Raw|ConvertFrom-Json).PSObject.Properties[$Case].Value
        if ($pub.case -ne $Case -or $pub.campaign -ne $Campaign -or $Cores -ne 2){throw 'Wrong transient replay case'}
        foreach ($entry in $pub.files.PSObject.Properties){
            if ((Get-FileHash -LiteralPath (Join-Path $work $entry.Name)).Hash -ne $entry.Value){throw 'Replay load checksum failed'}
        }
        $argsList=@('-b','nolist','-s','noread','-smp','-np',"$Cores",'-p','ansys','-j','file','-i','model.inp','-o','solve.out')
    }
    if ($Case.StartsWith('patch_')){
        $patchBook="$share\validation\contact_patch_inputs.json"
        if ($Case -match '^patch_(snug125_(?:nylon|aluminium))_Z_span(?:9|15)_(?:free|contact)_v1$') {
            $patchBook="$share\validation\snug125\$($Matches[1])_patch_inputs.json"
        }
        $pub=(Get-Content -LiteralPath $patchBook -Raw|ConvertFrom-Json).PSObject.Properties[$Case].Value
        if ($pub.input_sha256 -ne $stage.input_sha256 -or $pub.campaign -ne $Campaign -or $Cores -ne 2){throw 'Wrong local contact-patch input'}
        $argsList=@('-b','nolist','-s','noread','-smp','-np',"$Cores",'-p','ansys','-j','file','-i','model.inp','-o','solve.out')
    }
    if ($sharedWork){$argsList+=@('-dir',('"'+$work+'"'))}
    $p=Start-Process -FilePath $exe -WorkingDirectory $work -ArgumentList $argsList -PassThru
    Wait-NativeProcess $p $work 'file' $out $sharedWork
    $stage.exit=$p.ExitCode
    Copy-Item "$work\solve.out" $out
    Get-ChildItem $work -Filter '*.err' | Copy-Item -Destination $out
    $stage.native_clean=($p.ExitCode -eq 0) -and (Select-String -Path "$work\solve.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)
    if (!$stage.native_clean){
        if (!($surfaceJob -and $surfaceJob.kind -eq 'static' -and (Test-Path -LiteralPath "$work\file.rst") -and
            (Select-String -LiteralPath "$work\solve.out" -Pattern 'LOAD STEP\s+\d+\s+SUBSTEP\s+\d+\s+COMPLETED' -Quiet))){throw 'Native solve failed. Inspect solve.out.'}
        if (!$isDefaultSeat) {
            $proof=(Get-Content "$share\validation\partial_board_readbacks.json" -Raw|ConvertFrom-Json).PSObject.Properties[$Case].Value
            Copy-Item -LiteralPath "$share\.runtime\surface_partial_readbacks\$Case\partial_post.inp" -Destination $work
            if ((Get-FileHash "$work\partial_post.inp").Hash -ne $proof.input_sha256 -or $stage.input_sha256 -ne $proof.original_model_sha256){throw 'Partial readback input mismatch'}
            $pp=Start-Process -FilePath $exe -WorkingDirectory $work -ArgumentList @('-b','nolist','-s','noread','-smp','-np','1','-p','ansys','-dir',('"'+$work+'"'),'-j','partialpost','-i','partial_post.inp','-o','partial_post.out') -Wait -PassThru
            Copy-Item -LiteralPath "$work\partial_post.out" $out
            if ($pp.ExitCode -ne 0 -or !(Select-String -LiteralPath "$work\partial_post.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)){throw 'Partial whole-board readback failed'}
            Update 'solver_complete'
            return
        }
    }
    if ($surfaceJob -and $surfaceJob.kind -eq 'static'){
        $pp=Start-Process -FilePath $exe -WorkingDirectory $work -ArgumentList @('-b','nolist','-s','noread','-smp','-np','1','-p','ansys','-dir',('"'+$work+'"'),'-j','seatpost','-i','board_surface_post.inp','-o','board_surface_post.out') -Wait -PassThru
        Copy-Item "$work\board_surface_post.out" $out
        if ($pp.ExitCode -ne 0 -or !(Test-Path "$work\seat_contacts.csv") -or !(Test-Path "$work\seat_material.csv") -or
            !(Select-String -LiteralPath "$work\board_surface_post.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)){throw 'Native tab/contact/material readback failed'}
    }
    if ($forceReadback -or $Case -match '^(flush|stand3|snug125)_(nylon|aluminium)_static$' -or $Case -in @('stand3_nylon_mesh2_static','snug125_nylon_mesh3_static')) {
        if ($forceReadback) {
            Copy-Item -LiteralPath "$work\snug_force_post.inp" -Destination "$work\contact_post.inp"
        } else {
            Copy-Item -LiteralPath "$PSScriptRoot\contact_post.inp" -Destination $work
        }
        $pp=Start-Process -FilePath $exe -WorkingDirectory $work -ArgumentList @('-b','nolist','-s','noread','-smp','-np','1','-p','ansys','-dir',('"'+$work+'"'),'-j','casepost','-i','contact_post.inp','-o','contact_post.out') -Wait -PassThru
        Copy-Item "$work\contact_post.out" $out
        if ($forceReadback -and !(Test-Path "$work\snug_contact_force.csv")){throw 'Missing resultant readback'}
        if ($pp.ExitCode -ne 0 -or !(Test-Path "$work\case_contact.csv") -or !(Select-String -Path "$work\contact_post.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)){throw 'Native contact readback failed'}
    }
    Update 'solver_complete'
} catch {$stage.failure=$_.Exception.Message;Update 'failed';throw}

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
$active=@(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(ANSYS|ANSYS\d+|mapdl|mpiexec|hydra_pmi_proxy)$' })
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
        $pattern=if($Case -match '_enforced$'){'^file(?:[0-9]*)\.(?:db|mode|full|esav|emat|dsp|mlv)$'}elseif($Case -match '_motion_[XYZ]$'){'^file\.(?:db|mode|full|enf|mlv)$'}elseif($Case -match '_psd_'){'^file(?:[0-9]*)\.(?:db|mode|full|esav|emat|rst|dsp)$'}else{'^file(?:[0-9]*)\.(?:rdb|ldhi|r[0-9]{3,}|rst|dsp|emat|esav|full|db|rsm|rth|s[0-9]{2,})$'}
        $parents=@($manifest.files|Where-Object name -match $pattern)
        if ($parents.Count -lt 3) {throw 'Parent restart files missing'}
        $needed=($parents|Measure-Object bytes -Sum).Sum
        if (!(Test-Path -LiteralPath "$work\remote_psd.json") -and (Get-PSDrive C).Free -lt $needed+14000000000){throw "Insufficient space for parent and solver scratch"}
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
        & "$PSScriptRoot\motion_solve.ps1" -Work $work -Case $Case -Campaign $Campaign -Exe $exe
        $stage.exit=0
        Copy-Item -LiteralPath "$work\solve.out" $out
        Update 'solver_complete'
        return
    }
    if (Test-Path -LiteralPath "$work\local_job.json") {
        $spec=Get-Content "$work\local_job.json" -Raw|ConvertFrom-Json
        $stage.cores=$spec.cores
        Update 'solving'
        $localResult=& "$PSScriptRoot\local_solve.ps1" -Work $work -Case $Case -Exe $exe
        $stage.exit=$localResult.exit
        $stage.native_clean=$localResult.clean
        $stage.result_job=$localResult.job
        Copy-Item -LiteralPath "$work\solve.out" $out
        Update 'solver_complete'
        return
    }
    $surfaceJob=$null
    if ($Case -match '^flush_(nylon|aluminium)_surf1_(static|modal20|basis)$'){
        $surfaceJob=Get-Content -LiteralPath "$work\surface_job.json" -Raw|ConvertFrom-Json
        $pub=(Get-Content "$share\validation\board_surface_jobs.json" -Raw|ConvertFrom-Json).PSObject.Properties[$Case].Value
        if ($surfaceJob.case -ne $Case -or $stage.input_sha256 -ne $surfaceJob.model_sha256 -or
            (Get-FileHash "$work\surface_job.json").Hash -ne $pub.spec_sha256 -or [string]$surfaceJob.parent -ne $Parent){throw 'Wrong surface-contact job or parent'}
        if ($surfaceJob.kind -eq 'static' -and (Get-FileHash "$work\board_surface_post.inp").Hash -ne $surfaceJob.post_sha256){throw 'Wrong seating readback'}
    }
    Update 'solving'
    $argsList=@('-b','nolist','-s','noread','-dis','-np',"$Cores",'-p','ansys','-j','file','-i','model.inp','-o','solve.out')
    if ($Case.StartsWith('replay_')){
        $pub=(Get-Content "$share\validation\contact_replay_inputs.json" -Raw|ConvertFrom-Json).PSObject.Properties[$Case].Value
        if ($pub.case -ne $Case -or $pub.campaign -ne $Campaign -or $Cores -ne 2){throw 'Wrong transient replay case'}
        foreach ($entry in $pub.files.PSObject.Properties){
            if ((Get-FileHash -LiteralPath (Join-Path $work $entry.Name)).Hash -ne $entry.Value){throw 'Replay load checksum failed'}
        }
        $argsList=@('-b','nolist','-s','noread','-smp','-np',"$Cores",'-p','ansys','-j','file','-i','model.inp','-o','solve.out')
    }
    if ($Case.StartsWith('patch_')){
        $pub=(Get-Content "$share\validation\contact_patch_inputs.json" -Raw|ConvertFrom-Json).PSObject.Properties[$Case].Value
        if ($pub.input_sha256 -ne $stage.input_sha256 -or $pub.campaign -ne $Campaign -or $Cores -ne 2){throw 'Wrong local contact-patch input'}
        $argsList=@('-b','nolist','-s','noread','-smp','-np',"$Cores",'-p','ansys','-j','file','-i','model.inp','-o','solve.out')
    }
    $p=Start-Process -FilePath $exe -WorkingDirectory $work -ArgumentList $argsList -PassThru
    while (!$p.WaitForExit(1500)){
        $freeNow=(Get-PSDrive C).Free
        if ($freeNow -lt 14000000000 -and (Test-Path -LiteralPath "$work\STORAGE_STOP.txt") -and !$p.HasExited){
            # Stop only this job's process tree if it is in a linear phase that does not service file.abt.
            & taskkill.exe /PID $p.Id /T /F | Out-Null
            $p.WaitForExit()
            throw 'Critical scratch reserve reached; stopped the launched process tree, preserving guest files'
        }
        if ($freeNow -lt 17000000000 -and !(Test-Path -LiteralPath "$work\STORAGE_STOP.txt")){
            'nonlinear'|Set-Content -LiteralPath "$work\file.abt" -Encoding Ascii
            "Controlled stop requested at $([DateTime]::UtcNow.ToString('o'))"|Set-Content -LiteralPath "$work\STORAGE_STOP.txt"
        }
    }
    $p.Refresh()
    $stage.exit=$p.ExitCode
    Copy-Item "$work\solve.out" $out
    Get-ChildItem $work -Filter '*.err' | Copy-Item -Destination $out
    $stage.native_clean=($p.ExitCode -eq 0) -and (Select-String -Path "$work\solve.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)
    if (!$stage.native_clean){
        if (!($surfaceJob -and $surfaceJob.kind -eq 'static' -and (Test-Path -LiteralPath "$work\file.rst") -and
            (Select-String -LiteralPath "$work\solve.out" -Pattern 'LOAD STEP\s+\d+\s+SUBSTEP\s+\d+\s+COMPLETED' -Quiet))){throw 'Native solve failed. Inspect solve.out.'}
        $proof=(Get-Content "$share\validation\partial_board_readbacks.json" -Raw|ConvertFrom-Json).PSObject.Properties[$Case].Value
        Copy-Item -LiteralPath "$share\.runtime\surface_partial_readbacks\$Case\partial_post.inp" -Destination $work
        if ((Get-FileHash "$work\partial_post.inp").Hash -ne $proof.input_sha256 -or $stage.input_sha256 -ne $proof.original_model_sha256){throw 'Partial readback input mismatch'}
        $pp=Start-Process -FilePath $exe -WorkingDirectory $work -ArgumentList @('-b','nolist','-s','noread','-smp','-np','1','-p','ansys','-j','partialpost','-i','partial_post.inp','-o','partial_post.out') -Wait -PassThru
        Copy-Item -LiteralPath "$work\partial_post.out" $out
        if ($pp.ExitCode -ne 0 -or !(Select-String -LiteralPath "$work\partial_post.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)){throw 'Partial whole-board readback failed'}
        Update 'solver_complete'
        return
    }
    if ($surfaceJob -and $surfaceJob.kind -eq 'static'){
        $pp=Start-Process -FilePath $exe -WorkingDirectory $work -ArgumentList @('-b','nolist','-s','noread','-smp','-np','1','-p','ansys','-j','seatpost','-i','board_surface_post.inp','-o','board_surface_post.out') -Wait -PassThru
        Copy-Item "$work\board_surface_post.out" $out
        if ($pp.ExitCode -ne 0 -or !(Test-Path "$work\seat_contacts.csv") -or !(Test-Path "$work\seat_material.csv") -or
            !(Select-String -LiteralPath "$work\board_surface_post.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)){throw 'Native tab/contact/material readback failed'}
    }
    if ($Case -match '^(flush|stand3)_(nylon|aluminium)_static$') {
        Copy-Item -LiteralPath "$PSScriptRoot\contact_post.inp" -Destination $work
        $pp=Start-Process -FilePath $exe -WorkingDirectory $work -ArgumentList @('-b','nolist','-s','noread','-smp','-np','1','-p','ansys','-j','casepost','-i','contact_post.inp','-o','contact_post.out') -Wait -PassThru
        Copy-Item "$work\contact_post.out" $out
        if ($pp.ExitCode -ne 0 -or !(Test-Path "$work\case_contact.csv") -or !(Select-String -Path "$work\contact_post.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)){throw 'Native contact readback failed'}
    }
    Update 'solver_complete'
} catch {$stage.failure=$_.Exception.Message;Update 'failed';throw}

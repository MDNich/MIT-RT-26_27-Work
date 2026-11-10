# Use measured SMP timing only for the matching, previously undispatched local mesh.
function Get-LocalRuntime($Spec, [string]$Case, [string]$Campaign, [string]$Share) {
    $choice=[ordered]@{cores=[int]$Spec.cores;sealed_cores=[int]$Spec.cores;mode='SMP'}
    # The increment-control run compares with a four-core parent at common saved displacements.
    if ($Spec.snug_step_parent) {return $choice}
    $dir=Join-Path $Share 'validation\snug125'
    $audit=Join-Path $dir 'local_core_trial.json'
    if ($Case -notmatch '^snug125_(nylon|aluminium)_(lateral|damage)_[a-z0-9_]+_m15$' -or
        $Spec.cores -ne 4 -or $Spec.size_mm -ne 1.5 -or !(Test-Path -LiteralPath $audit)) {return $choice}
    try {
        $entry=Get-Content -LiteralPath $audit -Raw|ConvertFrom-Json
        $inputRecord=Join-Path $dir 'local_core_trial_input.json'
        $trial=Get-Content -LiteralPath $inputRecord -Raw|ConvertFrom-Json
        if ($entry.campaign -ne $Campaign -or $entry.mesh_sha256 -ne $Spec.case_mesh_sha256) {return $choice}
        if ($entry.case -ne 'snug125_nylon_clamp_smp12' -or $entry.parent -ne $trial.parent -or
            $entry.case -ne $trial.case -or $entry.mesh_sha256 -ne $trial.mesh_sha256 -or
            $entry.trial_input_record_sha256 -ne (Get-FileHash -LiteralPath $inputRecord).Hash -or
            $entry.selected_cores -notin 4,12 -or $entry.verified_runs.Count -ne 2 -or
            $entry.matched_ramp_states.Count -lt 3) {throw 'Inconsistent closed local SMP timing audit'}
        foreach ($r in $entry.verified_runs) {
            if ($r.case -notin $entry.parent,$entry.case) {throw 'Unexpected SMP timing source'}
            $folder=Join-Path $Share ".runtime\receipts\$Campaign\$($r.case)"
            if (!(Test-Path -LiteralPath "$folder\released.txt") -or
                $r.archive_sha256 -ne (Get-FileHash -LiteralPath "$folder\archived.json").Hash) {
                throw 'SMP timing archive identity mismatch'
            }
        }
        $choice.cores=[int]$entry.selected_cores
        $choice.trial_sha256=(Get-FileHash -LiteralPath $audit).Hash.ToLowerInvariant()
    } catch {
        $choice.cores=[int]$Spec.cores
        $choice.fallback_reason=$_.Exception.Message
    }
    return $choice
}

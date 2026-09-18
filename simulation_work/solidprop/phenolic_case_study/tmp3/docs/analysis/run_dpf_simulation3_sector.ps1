$ErrorActionPreference = "Stop"

$python = "C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe"
$root = "C:\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\solidprop\phenolic_case_study\tmp3\docs\analysis"
$rth = "C:\ansys_sector_sim2\testbed2_files\dp0\SYS-3\MECH"
$history = Join-Path $root "simulation3_sector_history_snapshot.csv"
$results = 0..9 | ForEach-Object { Join-Path $rth ("file{0}.rth" -f $_) }
$log = Join-Path $root "simulation3_sector_dpf_extract.log"

Remove-Item -Force -ErrorAction SilentlyContinue $log
Start-Transcript -Path $log -Force
try {
    $contourCsv = Join-Path $root "simulation3_sector_recession_to_pyrolysis_contours_vs_time.csv"
    $contourComplete = (Test-Path $contourCsv) -and ((Import-Csv $contourCsv).Count -eq 140)
    if ($contourComplete) {
        Write-Output "Reusing validated 140-state pyrolysis contours."
    }
    else {
        Write-Output "Extracting exact 140-state pyrolysis contours..."
        & $python -u `
            (Join-Path $root "dpf_extract_simulation3_sector_contour_timeseries.py") `
            $contourCsv `
            $history `
            @results
        if ($LASTEXITCODE -ne 0) { throw "Contour extraction failed with exit code $LASTEXITCODE." }
    }

    Write-Output "Extracting sparse radial and axial SVAR profiles..."
    & $python -u `
        (Join-Path $root "dpf_extract_simulation3_sector_svar_profiles.py") `
        (Join-Path $root "simulation3_sector_svar_radial_time_profiles_1pct.csv") `
        (Join-Path $root "simulation3_sector_svar_axial_time_profiles_1pct.csv") `
        $history `
        @results
    if ($LASTEXITCODE -ne 0) { throw "SVAR profile extraction failed with exit code $LASTEXITCODE." }
    Write-Output "SIMULATION3_DPF_COMPLETE"
}
finally {
    Stop-Transcript
}

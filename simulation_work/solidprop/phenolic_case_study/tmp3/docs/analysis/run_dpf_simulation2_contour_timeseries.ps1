param(
    [double]$MaxTime = 0.0
)

$ErrorActionPreference = "Stop"
$work = "C:\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\solidprop\phenolic_case_study"
$root = Join-Path $work "tmp3"
$run = Join-Path $work "tmp3_sim2\resume_runs\ScrResume_step16_v2_20260719"
$python = "C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe"
$script = Join-Path $root "docs\analysis\dpf_extract_simulation2_contour_timeseries.py"
$history = Join-Path $root "docs\analysis\simulation2_history_contour_snapshot.csv"
$output = Join-Path $root "docs\analysis\simulation2_recession_to_pyrolysis_contours_vs_time.csv"
$log = Join-Path $root "docs\analysis\simulation2_contour_timeseries_dpf.log"
$errorLog = Join-Path $root "docs\analysis\simulation2_contour_timeseries_dpf.err"
$pidFile = Join-Path $root "docs\analysis\simulation2_contour_timeseries_dpf.pid"
$arguments = @("-u", $script)

if ($MaxTime -gt 0.0) {
    $output = Join-Path $root "docs\analysis\simulation2_contour_timeseries_test.csv"
    $arguments += @("--max-time", $MaxTime.ToString([Globalization.CultureInfo]::InvariantCulture))
}

$arguments += @(
    $output,
    $history,
    (Join-Path $run "file0.rth"),
    (Join-Path $run "file1.rth"),
    (Join-Path $run "file2.rth"),
    (Join-Path $run "file3.rth"),
    (Join-Path $run "file4.rth"),
    (Join-Path $run "file5.rth"),
    (Join-Path $run "file6.rth"),
    (Join-Path $run "file7.rth"),
    (Join-Path $run "file8.rth"),
    (Join-Path $run "file9.rth")
)

Remove-Item -Force -ErrorAction SilentlyContinue $log, $errorLog, $pidFile
$process = Start-Process `
    -FilePath $python `
    -ArgumentList $arguments `
    -RedirectStandardOutput $log `
    -RedirectStandardError $errorLog `
    -WindowStyle Hidden `
    -PassThru
$process.Id | Set-Content -Path $pidFile -Encoding ASCII
Write-Output "Started DPF contour extractor with PID $($process.Id)."
exit 0

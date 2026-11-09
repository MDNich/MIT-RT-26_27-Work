# Preserve the study's scratch reserves while waiting for this particular MAPDL process tree.
function Wait-NativeProcess($Process, [string]$Directory, [string]$Job, [string]$Receipt, [bool]$SharedWork) {
    $stop = Join-Path $Directory 'STORAGE_STOP.txt'
    while (!$Process.WaitForExit(1500)) {
        $free = (Get-PSDrive C -ErrorAction Stop).Free
        $critical = $SharedWork -and (Test-Path -LiteralPath (Join-Path $Receipt 'host_critical.json'))
        $soft = $SharedWork -and (Test-Path -LiteralPath (Join-Path $Receipt 'host_stop.json'))
        if (($free -lt 17000000000 -or $soft -or $critical) -and !(Test-Path -LiteralPath $stop)) {
            $jobNames = @($Job)
            $listing = Join-Path $Directory 'solve.out'
            if ((Test-Path -LiteralPath $listing) -and (Select-String -Quiet -LiteralPath $listing -Pattern ('CURRENT JOBNAME=' + [Regex]::Escape($Job) + '0\s'))) {
                $jobNames += ($Job+'0')
            }
            foreach ($name in $jobNames) {
                'nonlinear' | Set-Content -LiteralPath (Join-Path $Directory ($name+'.abt')) -Encoding Ascii
            }
            "Controlled stop requested at $([DateTime]::UtcNow.ToString('o'))" | Set-Content -LiteralPath $stop
        }
        if (($free -lt 14000000000 -or $critical) -and !$Process.HasExited) {
            & taskkill.exe /PID $Process.Id /T /F | Out-Null
            $Process.WaitForExit()
            throw 'Critical scratch reserve reached; stopped the launched process tree, preserving its files'
        }
    }
    $Process.Refresh()
}

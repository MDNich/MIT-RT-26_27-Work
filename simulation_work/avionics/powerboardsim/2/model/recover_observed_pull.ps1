# Postprocess the original four-core snug pull if its older runner failed only at the final POST1 readback.
# Called at a serial boundary, before the next structural process starts.
param([Parameter(Mandatory)][string]$Campaign,[switch]$InspectOnly)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
if ($Campaign -ne 'nov08_01') {return}
$case='snug125_nylon_lateral_friction_locked_pin1_m15'
$share=Split-Path $PSScriptRoot
$receipt=Join-Path $share ".runtime\receipts\$Campaign\$case"
$work=Join-Path "C:\Temp\PBCaseStudy\$Campaign" $case
$statusFile=Join-Path $receipt 'status.json'
if (!(Test-Path -LiteralPath $statusFile)) {return}
$readStatus=Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json
$observedFile=Join-Path $receipt 'observed_solver_exit.json'
if ($readStatus.phase -ne 'failed' -or $readStatus.failure -ne 'Local local_post result readback failed') {return}
$stage=Join-Path $work 'recovered_post'
$archive=Join-Path $share ".runtime\archive\$Campaign\$case"
$identity='6c60a5100317f0eac6e01ff18bd76bd464852aa6fffd38f635ad72e013865352'
if ($readStatus.case -ne $case -or $readStatus.cores -ne 4 -or $readStatus.work -ne $work -or
    $readStatus.input_sha256 -ne $identity -or (Test-Path "$work\STORAGE_STOP.txt")) {throw 'Unexpected failed pull identity'}
$obs=Get-Content -LiteralPath $observedFile -Raw | ConvertFrom-Json
$attached=Get-Content "$receipt\exit_observer_started.json" -Raw | ConvertFrom-Json
foreach ($field in 'case','campaign','input_sha256','observer_pid','runner_pid','native_launcher_pid','solver_pid','native_start_utc','attached_utc') {
    if ($obs.$field -ne $attached.$field) {throw "Observer identity mismatch: $field"}
}
$dispatch=Get-Content "$receipt\dispatch.json" -Raw | ConvertFrom-Json
if ($obs.case -ne $case -or $obs.campaign -ne $Campaign -or $obs.input_sha256 -ne $identity -or
    $obs.runner_pid -ne $dispatch.ProcessId -or $null -eq $obs.exit_code -or $obs.exit_code -eq 0 -or
    [datetime]$obs.exit_utc -lt [datetime]$obs.attached_utc) {throw 'Missing original structural exit evidence'}
$spec=Get-Content "$work\local_job.json" -Raw | ConvertFrom-Json
$catalog=Get-Content "$share\validation\snug125\local_inputs_m15.json" -Raw | ConvertFrom-Json
$entry=$catalog.PSObject.Properties[$case].Value
if ($entry.input_sha256 -ne $identity -or (Get-FileHash "$work\local_job.json").Hash -ne $entry.spec_sha256 -or
    $spec.case -ne $case -or $spec.job -ne 'pull' -or $spec.files.'model.inp' -ne $identity) {throw 'Wrong original local fixture'}
foreach ($f in $spec.files.PSObject.Properties) {
    if ((Get-FileHash (Join-Path $work $f.Name)).Hash -ne $f.Value) {throw "Changed sealed file: $($f.Name)"}
}
function Has-Line([string]$File,[string]$Pattern) {return (Select-String -LiteralPath (Join-Path $work $File) -Pattern $Pattern -Quiet)}
if (!(Has-Line 'solve.out' 'Solution not converged') -or !(Has-Line 'solve.out' 'RUN COMPLETED') -or
    !(Has-Line 'solve.out' 'LOAD STEP\s+3\s+SUBSTEP\s+\d+\s+COMPLETED') -or
    !(Has-Line 'moving.out' 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b') -or
    !(Test-Path "$work\moving_supports.csv") -or (Test-Path "$work\solved.db")) {throw 'Failure differs from the missing solved database case'}
$files=@('history.csv','nodal.csv','element_top.csv','element_bottom.csv','contact_history.csv','balance.csv','contact_detail.csv','moment_balance.csv')
if ($InspectOnly) {return [pscustomobject]@{case=$case;exit=$obs.exit_code;tables=$files}}
$processes=@(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
    $_.Name -match '^(ANSYS(261)?|mapdl|mpiexec|hydra_pmi_proxy)\.exe$' -or
    ($_.ProcessId -eq $obs.runner_pid -and $_.CommandLine -like "*\native_run.ps1 -Case $case -Campaign $Campaign*")
})
if ($processes.Count) {throw 'A solver or the original runner is still active'}
if ((Get-PSDrive C).Free -lt 17000000000) {throw 'Insufficient guest scratch for partial readback'}
if (!('PBRecoveryVolume' -as [type])) {
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class PBRecoveryVolume { [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern bool GetDiskFreeSpaceEx(string dir,out ulong avail,out ulong total,out ulong free); }'
}
[UInt64]$available=0;[UInt64]$total=0;[UInt64]$free=0
$needed=(Get-ChildItem -LiteralPath $work -File | Measure-Object Length -Sum).Sum
if (![PBRecoveryVolume]::GetDiskFreeSpaceEx($share,[ref]$available,[ref]$total,[ref]$free) -or
    $available -lt (400000000000 + $needed)) {throw 'Host archive reserve unavailable'}
if (Test-Path "$receipt\original_readback_failure.json") {throw 'Prior recovery receipt requires inspection'}
$lease=[IO.File]::Open("$receipt\recovery.lock",'OpenOrCreate','ReadWrite','None')
try {
    # Each interrupted stage remains intact for inspection. In particular an uncertain POST1 is never relaunched.
    if (Test-Path -LiteralPath $stage) {throw 'Recovery workspace exists; inspect the prior readback'}
    New-Item -ItemType Directory -Path $stage | Out-Null
    Copy-Item -LiteralPath $statusFile -Destination "$receipt\original_readback_failure.json" -ErrorAction Stop
    $failedHash=(Get-FileHash $statusFile).Hash
    if ((Get-FileHash "$receipt\original_readback_failure.json").Hash -ne $failedHash) {throw 'Original failure copy differs'}
    New-Item -ItemType Directory -Path $archive -Force | Out-Null
    $rst=Join-Path $work 'pull.rst'
    $hash=(Get-FileHash $rst).Hash
    $saved=Join-Path $archive 'pull.rst'
    if (!(Test-Path -LiteralPath $saved)) {
        $tmp="$saved.readback-backup"
        Copy-Item -LiteralPath $rst -Destination $tmp
        if ((Get-FileHash $tmp).Hash -ne $hash) {throw 'Closed RST backup differs'}
        Move-Item -LiteralPath $tmp -Destination $saved
    }
    if ((Get-FileHash $saved).Hash -ne $hash) {throw 'Existing RST backup differs'}
    New-Item -ItemType HardLink -Path "$stage\pull.rst" -Target $rst | Out-Null
    foreach ($f in 'model.db','local_post.inp') {
        Copy-Item -LiteralPath "$work\$f" -Destination $stage
        if ((Get-FileHash "$stage\$f").Hash -ne (Get-FileHash "$work\$f").Hash) {throw "Copied input differs: $f"}
    }
    . "$PSScriptRoot\local_partial_post.ps1"
    $stem=Get-LocalPullPost $stage $case 'pull' $false
    $postHash=(Get-FileHash "$stage\$stem.inp").Hash
    if ($stem -ne 'partial_local_post' -or $postHash -ne '2cb57f5ebafeaaf728c4597aa4dc8bbb2627898a0095629ec6871b712936457e') {throw 'Unexpected derived POST1 control'}
    $exe='C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
    $env:ANSYSLMD_LICENSE_FILE='1055@localhost'
    $post=Start-Process -FilePath $exe -WorkingDirectory $stage -PassThru -Wait -ArgumentList @(
        '-b','nolist','-s','noread','-smp','-np','1','-p','preppost','-j',$stem,'-i',"$stem.inp",'-o',"$stem.out")
    if ($post.ExitCode -ne 0 -or !(Select-String "$stage\$stem.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)) {throw 'Partial POST1 job failed'}
    if ((Get-FileHash $rst).Hash -ne $hash) {throw 'Original result differs after readback'}
    $outputs=[ordered]@{}; $previous=[ordered]@{}
    foreach ($file in $files) {
        $source=Join-Path $stage $file
        if ((Get-Item $source).Length -lt 1) {throw "Missing recovered table: $file"}
        $outputs[$file]=(Get-FileHash $source).Hash
    }
    foreach ($file in @($files + @("$stem.inp","$stem.out"))) {
        $source=Join-Path $stage $file
        $destination=Join-Path $work $file
        if (Test-Path -LiteralPath $destination) {
            $previous[$file]=(Get-FileHash $destination).Hash
            $backup=Join-Path $work ("before_readback_"+$file)
            if (Test-Path $backup) {throw 'Reserved backup name exists'}
            Move-Item -LiteralPath $destination -Destination $backup
            if ((Get-FileHash $backup).Hash -ne $previous[$file]) {throw 'Old output changed during preservation'}
        }
        Copy-Item -LiteralPath $source -Destination $destination
        if ((Get-FileHash $destination).Hash -ne (Get-FileHash $source).Hash) {throw 'Final POST1 copy differs'}
    }
    # Free only this hard link. The verified immutable host backup and the original guest RST still exist.
    Remove-Item -LiteralPath "$stage\pull.rst"
    $record=[ordered]@{case=$case;campaign=$Campaign;input_sha256=$identity;original_status_sha256=$failedHash;
        observed_exit_sha256=(Get-FileHash $observedFile).Hash;original_solver_exit=$obs.exit_code;rst_sha256=$hash;
        post_input_sha256=$postHash;post_exit=$post.ExitCode;outputs=$outputs;original_table_hashes=$previous}
    $record|ConvertTo-Json -Depth 4|Set-Content "$receipt\closed_post_recovery.json" -Encoding UTF8
    $fields=[ordered]@{}
    foreach ($item in $readStatus.PSObject.Properties) {$fields[$item.Name]=$item.Value}
    $fields.phase='solver_complete';$fields.exit=[int]$obs.exit_code;$fields.native_clean=$false;$fields.result_job='pull'
    $fields.updated=[datetime]::UtcNow.ToString('o');$fields.readback_recovery_sha256=(Get-FileHash "$receipt\closed_post_recovery.json").Hash
    $fields|ConvertTo-Json -Depth 4|Set-Content "$receipt\recovered_status.tmp" -Encoding UTF8
    Move-Item "$receipt\recovered_status.tmp" $statusFile -Force
    Copy-Item "$work\solve.out" $receipt
} finally {$lease.Dispose()}

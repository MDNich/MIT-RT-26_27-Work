param([Parameter(Mandatory)][ValidatePattern('^projection_readback_snug125_aluminium_project3_static_nov08_01$')][string]$Trial)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$work=Join-Path "$root\.runtime" $Trial
$guard="C:\Temp\PBCaseStudy\$Trial"
try {
    if ((Get-PSDrive C).Free -lt 18000000000 -or (Test-Path $guard)) {throw 'Scratch or existing readback guard'}
    $active=@(Get-Process -ea SilentlyContinue|Where-Object {$_.ProcessName -match '^(ANSYS|ANSYS\d+|mapdl|mpiexec|hydra_pmi_proxy)$'})
    if ($active.Count){throw 'Native solver already active'}
    New-Item -ItemType Directory $guard | Out-Null
    $req=Get-Content "$work\request.json" -Raw | ConvertFrom-Json
    if ($Trial -ne ('projection_readback_'+$req.case+'_'+$req.campaign)){throw 'Unexpected job identity'}
    foreach ($entry in @(@('control.inp',$req.post_input_sha256),@('file.rdb',$req.source_rdb_sha256),@('file.rst',$req.source_rst_sha256))){
        if ((Get-FileHash -LiteralPath (Join-Path $work $entry[0])).Hash -ne $entry[1]){throw 'Readback source mismatch'}
    }
    $exe='C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
    $env:ANSYSLMD_LICENSE_FILE='1055@localhost'
    $job=Start-Process $exe -WorkingDirectory $work -ArgumentList @('-b','nolist','-s','noread','-smp','-np','1','-p','ansys','-dir',('"'+$work+'"'),'-j','projpost','-i','control.inp','-o','control.out') -Wait -PassThru
    if ($job.ExitCode -ne 0 -or !(Select-String -LiteralPath "$work\control.out" -Pattern 'PROJECTION_READBACK_FINISHED' -Quiet)){throw 'Native postprocessor rejected the readback'}
    '0'|Set-Content "$work\exit.txt" -Encoding Ascii
} catch {$_.Exception.Message|Set-Content "$work\failed.txt" -Encoding Ascii;throw}

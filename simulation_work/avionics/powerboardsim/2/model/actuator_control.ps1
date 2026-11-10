param([Parameter(Mandatory)][ValidateSet('board_actuator_control_v1','seat_surface_control_v1','patch_table_control_v1','spherical_bearing_control_v1','snug_transient_control_v1')][string]$Trial)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$src="$root\.runtime\$Trial"
$work="C:\Temp\PBCaseStudy\$Trial"
$exe='C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
$env:ANSYSLMD_LICENSE_FILE='1055@localhost'
try {
    if ((Get-PSDrive C).Free -lt 18000000000 -or (Test-Path $work)){throw 'Guard or existing test; inspect before retrying'}
    $active=@(Get-Process -ea SilentlyContinue|Where-Object {$_.ProcessName -match '^(ANSYS|ANSYS\d+|mapdl|mpiexec|hydra_pmi_proxy)$'})
    if ($active.Count){throw 'Another solver is active'}
    New-Item -ItemType Directory $work|Out-Null
    Copy-Item -LiteralPath "$src\control.inp" -Destination $work
    if ((Get-FileHash "$src\control.inp").Hash -ne (Get-FileHash "$work\control.inp").Hash){throw 'Staging mismatch'}
    if ($Trial -in 'patch_table_control_v1','snug_transient_control_v1'){
        $book=if ($Trial -eq 'snug_transient_control_v1'){'snug125/transient_control_input.json'}else{'patch_table_control_input.json'}
        $meta=Get-Content -LiteralPath "$root\validation\$book" -Raw|ConvertFrom-Json
        foreach($entry in $meta.files.PSObject.Properties){
            if ($entry.Name -notmatch '^[a-z]+\.dat$|^control\.inp$'){throw 'Unexpected control input'}
            if ($entry.Name -ne 'control.inp'){Copy-Item -LiteralPath (Join-Path $src $entry.Name) -Destination $work}
            if ((Get-FileHash -LiteralPath (Join-Path $work $entry.Name)).Hash -ne $entry.Value){throw 'Control input mismatch'}
        }
    }
    $p=Start-Process $exe -WorkingDirectory $work -Wait -PassThru -ArgumentList '-b nolist -s noread -p ansys -smp -np 1 -j file -i control.inp -o control.out'
    foreach ($n in 'control.out','file.err','actuator_static.csv','actuator_modal.csv','seat_control.csv','control_response.csv','bearing_control.csv','twoblock.nlh','twoblock.err','twoblock.out'){
        if (Test-Path "$work\$n"){Copy-Item "$work\$n" -Destination $src}
    }
    if ($Trial -eq 'snug_transient_control_v1' -and $p.ExitCode -eq 0) {
        $source=Join-Path $work 'twoblock.rst'
        $target=Join-Path $src 'twoblock.rst'
        $hash=(Get-FileHash -LiteralPath $source).Hash.ToLower()
        if (!(Test-Path -LiteralPath $target)) {Copy-Item -LiteralPath $source -Destination $target}
        if ((Get-FileHash -LiteralPath $target).Hash.ToLower() -ne $hash){throw 'Two-block RST archive mismatch'}
        @{source=$source;bytes=(Get-Item -LiteralPath $source).Length;sha256=$hash} | ConvertTo-Json | Set-Content (Join-Path $src 'rst_copy.json') -Encoding UTF8
    }
    $p.ExitCode|Set-Content "$src\exit.txt" -Encoding UTF8
} catch {$_.Exception.Message|Set-Content "$src\failed.txt";throw}

param([Parameter(Mandatory)][ValidateSet('shared_dmp_io_v1')][string]$Trial)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$src=Join-Path $root ".runtime\$Trial"
$guard="C:\Temp\PBCaseStudy\$Trial"
$exe='C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
$env:ANSYSLMD_LICENSE_FILE='1055@localhost'
try {
    if ((Test-Path $guard) -or (Test-Path "$src\work") -or (Test-Path "$src\exit.txt")) {throw 'Existing control directory'}
    $active=@(Get-Process -ea SilentlyContinue | Where-Object {$_.Name -match '^(ANSYS|ANSYS\d+|mapdl|mpiexec|hydra_pmi_proxy)$'})
    if ($active.Count){throw 'Active native solver'}
    $initial=(Get-PSDrive C).Free
    if ($initial -lt 18000000000){throw 'Insufficient guest reserve'}
    New-Item -ItemType Directory $guard -ErrorAction Stop|Out-Null
    $profile=Get-Content "$root\validation\shared_dmp_control_input.json" -Raw|ConvertFrom-Json
    $a=Join-Path $src 'work\static'
    $b=Join-Path $src 'work\modal'
    foreach($item in @(@($a,'control.inp'),@($b,'modal.inp'))) {
        $path=$item[0];$deck=$item[1]
        New-Item -ItemType Directory -Force $path|Out-Null
        Copy-Item -LiteralPath "$src\$deck" -Destination $path
        if ((Get-FileHash "$path\$deck").Hash -ne $profile.files.PSObject.Properties[$deck].Value){throw 'Wrong control deck'}
    }
    function Run([string]$path,[string]$deck) {
        $arguments=@('-b','nolist','-s','noread','-dis','-np','12','-p','ansys','-dir',('"' + $path + '"'),'-j','file','-i',$deck,'-o','solve.out')
        $p=Start-Process -FilePath $exe -WorkingDirectory $path -ArgumentList $arguments -PassThru -Wait
        if($p.ExitCode -ne 0 -or !(Select-String -LiteralPath "$path\solve.out" -Pattern 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b' -Quiet)){throw "Native control failed in $path"}
        return $p.ExitCode
    }
    $first=Run $a 'control.inp'
    $family=@(Get-ChildItem -LiteralPath $a -File|Where-Object { $_.Name -match '^file\d*\.(?:rdb|ldhi|r\d+|s\d+|db|rst|dsp|emat|esav|full)$' })
    if ($family.Count -lt 3 -or !(Test-Path "$a\file.rdb")) {throw 'Static restart family missing'}
    foreach($f in $family) {
        Copy-Item -LiteralPath $f.FullName -Destination $b
        if ((Get-FileHash $f.FullName).Hash -ne (Get-FileHash "$b\$($f.Name)").Hash){throw 'Restart copy mismatch'}
    }
    $second=Run $b 'modal.inp'
    @{trial=$Trial;static_exit=$first;modal_exit=$second;initial_free=$initial;final_free=(Get-PSDrive C).Free}|ConvertTo-Json | Set-Content "$src\result.json" -Encoding UTF8
    0|Set-Content "$src\exit.txt"
} catch {
    $why=$_.Exception.Message
    $alive=@(Get-Process -ErrorAction Stop|Where-Object {$_.Name -match '^(ANSYS|ANSYS\d+|mapdl|mpiexec|hydra_pmi_proxy)$'})
    if (!$alive.Count -and (Test-Path -LiteralPath $guard)) {
        $why|Set-Content "$src\closed_failure.txt"
        1|Set-Content "$src\exit.txt"
    } else {
        $why|Set-Content "$src\failed.txt"
    }
    throw
}

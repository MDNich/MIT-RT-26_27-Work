function Get-LocalPullPost([string]$Work, [string]$Case, [string]$Job, [bool]$Clean) {
    if ($Clean -or $Job -ne 'pull' -or $Case -notlike 'snug125_*') {return 'local_post'}
    $original=Join-Path $Work 'local_post.inp'
    if ((Get-FileHash -LiteralPath $original).Hash -ne 'decfbd958cda21fb5ecec7003164f2d8b9e9a1c9046633b7643e555b1d391fee') {return 'local_post'}
    if (!(Test-Path -LiteralPath (Join-Path $Work 'model.db') -PathType Leaf)) {throw 'Missing original local model database for partial readback'}

    # The archived flush partial used this exact database selection and five diagnostic-set guards.
    $text=[IO.File]::ReadAllText($original).Replace('RESUME,solved,db','RESUME,model,db')
    $text=$text.Replace("SET,,,,,,,II`n","SET,,,,,,,II`n*GET,ESUB,ACTIVE,0,SET,SBST`n*IF,ESUB,EQ,999999,THEN`n*CYCLE`n*ENDIF`n")
    $sha=[Security.Cryptography.SHA256]::Create()
    try {$control=[BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::ASCII.GetBytes($text))).Replace('-','')}
    finally {$sha.Dispose()}
    if ($control -ne '1c46f02e988b705cd186635446737961a05467ce0d6dd912626f928fa352db33') {throw 'Historical postprocessing control differs'}

    # Carry the accepted set number into the terminal displacement and two shell-face exports.
    $text=$text.Replace("*GET,TT,ACTIVE,0,SET,TIME`n*GET,UXP","PBLAST=II`n*GET,TT,ACTIVE,0,SET,TIME`n*GET,UXP")
    $text=$text.Replace("SET,LAST`nRSYS,0`n*CFOPEN,nodal","SET,,,,,,,PBLAST`nRSYS,0`n*CFOPEN,nodal")
    $text=$text.Replace("SET,LAST`nCMSEL,S,NICKEL`nSHELL,BOT","SET,,,,,,,PBLAST`nCMSEL,S,NICKEL`nSHELL,BOT")
    if ([regex]::Matches($text,'(?m)^PBLAST=II$').Count -ne 1 -or [regex]::Matches($text,'(?m)^SET,,,,,,,PBLAST$').Count -ne 2) {throw 'Partial final-state selection mismatch'}
    $out=Join-Path $Work 'partial_local_post.inp'
    if (Test-Path -LiteralPath $out) {
        if ([IO.File]::ReadAllText($out) -cne $text) {throw 'Reserved partial post input already exists with different contents'}
    } else {[IO.File]::WriteAllText($out,$text,[Text.Encoding]::ASCII)}
    return 'partial_local_post'
}

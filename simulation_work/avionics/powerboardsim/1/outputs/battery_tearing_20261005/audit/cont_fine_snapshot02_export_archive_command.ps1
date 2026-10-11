$ErrorActionPreference='Stop'; $d='C:\Temp\PBTear26_cont_fine_snapshot02';
if((Test-Path "$d\tear.lock") -or (Test-Path "$d\post.lock")){throw 'Runtime active'};
if(Test-Path 'C:\Temp\PBTear26_cont_fine_snapshot02\post_exports.zip'){throw 'Archive exists; inspect before repeating'};
$files=Get-ChildItem $d -File | Where-Object {$_.Extension -in '.csv','.out','.err','.txt','.db','.log','.ldhi','.mntr','.stat'};
$manifest=@($files | ForEach-Object {[PSCustomObject]@{name=$_.Name;length=$_.Length;sha256=(Get-FileHash $_.FullName).Hash.ToLower()}});
$manifest | ConvertTo-Json | Set-Content "$d\post_exports_manifest.json" -Encoding UTF8;
$paths=@($files.FullName)+@("$d\post_exports_manifest.json");
Compress-Archive -Path $paths -DestinationPath 'C:\Temp\PBTear26_cont_fine_snapshot02\post_exports.zip';
(Get-FileHash 'C:\Temp\PBTear26_cont_fine_snapshot02\post_exports.zip').Hash.ToLower()

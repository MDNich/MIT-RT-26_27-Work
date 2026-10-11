$ErrorActionPreference='Stop'
$d='C:\Temp\PBTear26_cont_fine_snapshot02'
if((Test-Path "$d\tear.lock") -or (Test-Path "$d\post.lock") -or (Test-Path "$d\balancecheck.lock")){throw 'Snapshot active'}
if((Test-Path "$d\balancecheck.out") -or (Test-Path "$d\balance_check.dat")){throw 'Diagnostic exists; inspect'}
$l=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25
if(($l -join "`n") -notmatch 'Total of 0 licenses? in use'){throw 'PrepPost occupied'}
[IO.File]::WriteAllBytes("$d\balance_check.dat",[Convert]::FromBase64String('L0JBVENIClJFU1VNRSxtb2RlbCxkYgovUE9TVDEKRklMRSx0ZWFyLHJzdApTRVQsMTIsMwpBTExTRUwsQUxMCi9DT00sSU5ERVBFTkRFTlRfQUxMX1JFQUNUSU9OU19BVF9NQVhfU05BUFNIT1RfWl9JTUJBTEFOQ0UKUFJSU09MLEYKL0NPTSxGT1VSX0NMQU1QX1BJTE9UUwpOU0VMLFMsTk9ERSwsMTEyMzQKTlNFTCxBLE5PREUsLDEyODk5Ck5TRUwsQSxOT0RFLCwxNDU2NApOU0VMLEEsTk9ERSwsMTYyMjkKUFJSU09MLEYKL0NPTSxCQVRURVJZX1BJTE9UX09OTFlfWF9QUkVTQ1JJQkVECk5TRUwsUyxOT0RFLCw5NTY5ClBSUlNPTCxGCkZJTklTSAovRVhJVCxOT1NBVkUK'))
if((Get-FileHash "$d\balance_check.dat").Hash.ToLower() -ne 'd099c921e89207d3ae3ba758f5acff5fc623e5c30f673c728acf0bc68fa73765'){throw 'Hash mismatch'}
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -s noread -smp -np 1 -p preppost -j balancecheck -i balance_check.dat -o balancecheck.out' -WorkingDirectory $d -PassThru
$p.Id

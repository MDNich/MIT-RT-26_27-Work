"""Read-only extraction of a coupon's converged result sets; never invokes SOLVE."""
from pathlib import Path
import subprocess,sys,re,shutil
S=Path(__file__).resolve().parent.parent
case=sys.argv[1];D=S/'runtime'/case;rt=r'C:\Temp\PBTear26_'+case
def win(p):return 'Z:'+str(p).removeprefix('/Users/mdn').replace('/','\\')
shutil.copy2(S/'sources/coupon_diagnostic.dat',D/'diagnostic.dat')
ps=f"""
$ErrorActionPreference='Stop'
if(Test-Path '{rt}\\tear.lock'){{throw 'Coupon still active'}}
$lic=& 'C:\\Program Files\\ANSYS Inc\\v261\\licensingclient\\winx64\\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){{throw 'PrepPost seat busy'}}
Copy-Item '{win(D)}\\diagnostic.dat' '{rt}\\diagnostic.dat'
$p=Start-Process 'C:\\Program Files\\ANSYS Inc\\v261\\ansys\\bin\\winx64\\ANSYS261.exe' -ArgumentList '-b nolist -s noread -smp -np 1 -p preppost -j diag -i diagnostic.dat -o diagnostic.out' -WorkingDirectory '{rt}' -PassThru -Wait
Copy-Item '{rt}\\accepted_history.csv','{rt}\\diagnostic.out','{rt}\\diag.err' '{win(D)}'
$p.ExitCode
"""
r=subprocess.run([sys.executable,str(S/'sources/vm_ps.py')],input=ps,text=True,capture_output=True,timeout=55)
print(r.stdout)
if r.returncode:raise RuntimeError(r.stderr)
t=(D/'diagnostic.out').read_text()
assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',t)
print('Converged-only coupon export verified')

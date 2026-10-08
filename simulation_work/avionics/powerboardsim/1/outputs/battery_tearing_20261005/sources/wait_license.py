"""Wait for an unused structural seat, then attempt exactly one guarded launch."""
from pathlib import Path
import subprocess,sys,time,re,datetime
S=Path(__file__).resolve().parent
case=sys.argv[1]
for i in range(120):
    if (S.parent/'runtime'/case/'SOLVE_STARTED.json').exists():
        print('Already launched; no second launch.',flush=True)
        break
    r=subprocess.run([sys.executable,str(S/'vm_ps.py')],input=r"& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f ansys -c 1055@MARCDNICHITBF25",capture_output=True,text=True,timeout=50)
    if r.returncode==0 and re.search(r'Total of 0 licenses? in use',r.stdout):
        subprocess.run([sys.executable,str(S/'native.py'),case,'solve'],check=True)
        break
    if i%6==0:print(datetime.datetime.now().isoformat(),'Waiting for structural license',flush=True)
    time.sleep(10)
else:
    print('No launch; structural license remained occupied.',flush=True)

"""Read-only native preflights for the prepared sensitivity cases. Never solves."""
from pathlib import Path
import json,subprocess,sys,time
S=Path(__file__).resolve().parent.parent
for c in json.loads((S/'audit/sensitivity_plan.json').read_text()):
    case=c['case'];D=S/'runtime'/case
    if (D/'PREFLIGHT_PASSED.txt').exists():continue
    if not (D/'PREFLIGHT_STARTED.json').exists():
        subprocess.run([sys.executable,str(S/'sources/native.py'),case,'preflight'],check=True)
    pid=int(json.loads((D/'PREFLIGHT_STARTED.json').read_text())['pid'])
    for i in range(18):
        time.sleep(3)
        r=subprocess.run([sys.executable,str(S/'sources/vm_ps.py')],
            input=f"if(Get-Process -Id {pid} -ErrorAction SilentlyContinue){{'RUNNING'}}else{{'FINISHED'}}",
            capture_output=True,text=True,check=True,timeout=30)
        if 'FINISHED' in r.stdout:break
    else:raise RuntimeError('Preflight still active: '+case)
    subprocess.run([sys.executable,str(S/'sources/native.py'),case,'check'],check=True)
    print('PASSED: '+case,flush=True)

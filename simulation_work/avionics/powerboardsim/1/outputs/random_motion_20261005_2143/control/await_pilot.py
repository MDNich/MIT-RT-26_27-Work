from pathlib import Path
import subprocess,time,re,datetime
T=Path(__file__).resolve().parents[1];P=T.parents[1];V=P/'outputs/video_4k60_20261005_1928/control/vm.py';N=T/'control/native.py'
O=T/'pilot_X_smp_v2';out=(O/'preflight.out').read_text();assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',out);assert re.search(r'NUMBER OF WARNING\s+MESSAGES ENCOUNTERED=\s*0',out)
assert not (O/'SOLVE_STARTED.txt').exists()
ps=r"""$l=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f ansys -c 1055@MARCDNICHITBF25
if(($l -join ' ') -match 'Total of 0 licenses? in use' -and -not(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue)){'READY'}else{'BUSY'}
"""
for i in range(180):
 r=subprocess.run(['python3',str(V)],input=ps,text=True,capture_output=True)
 if r.returncode:raise RuntimeError(r.stderr)
 if 'READY' in r.stdout:
  subprocess.run(['python3',str(N),'run',O.name],check=True)
  (T/'pipeline_status.txt').write_text('SMP transient pilot launched at '+datetime.datetime.now().isoformat()+'\n');print('LAUNCHED',flush=True);break
 if i%6==0:print('Waiting for coordinated structural seat '+datetime.datetime.now().isoformat(),flush=True)
 time.sleep(10)
else:raise TimeoutError('Structural seat remains occupied; pilot not launched')

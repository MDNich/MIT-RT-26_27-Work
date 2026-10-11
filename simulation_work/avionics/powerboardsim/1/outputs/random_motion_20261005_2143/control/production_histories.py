from pathlib import Path
import subprocess,time,datetime,json,re,sys
T=Path(__file__).resolve().parents[1];N=T/'control/native.py';V=T.parents[1]/'outputs/video_4k60_20261005_1928/control/vm.py'
assert(T/'pilot_X_smp_v2/ACCEPTED.json').exists();assert(T/'pilot_expand_nodal/NUMERICS_ACCEPTED.json').exists()
def status(s):
 line=datetime.datetime.now().isoformat()+' '+s;print(line,flush=True);(T/'pipeline_status.txt').write_text(line+'\n')
def checkpause():
 if (T/'PAUSE_REQUESTED.txt').exists():status('PAUSED before next action');sys.exit(0)
def vm(s):
 p=subprocess.run(['python3',str(V)],input=s,text=True,capture_output=True);p.check_returncode();return p.stdout
for axis in 'XYZ':
 checkpause();name='transient_'+axis;O=T/name
 if (O/'ACCEPTED.json').exists():continue
 if (O/'SOLVE_STARTED.txt').exists():
  assert '--continue-existing' in sys.argv, 'Existing solve needs explicit inspection'
  status('Monitoring already started '+name)
 else:
  status('Staging '+name);subprocess.run(['python3',str(N),'stage',name],check=True)
  start=time.monotonic()
  while not (O/'preflight_exit.txt').exists():
   checkpause();assert time.monotonic()-start<600;time.sleep(5)
  checkpause();status('Solving '+name);subprocess.run(['python3',str(N),'run',name],check=True)
  time.sleep(10)
 rt=json.loads((O/'manifest.json').read_text())['runtime'];start=time.monotonic()
 while True:
  result=vm("$rt='"+rt+"'\nif(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){'RUNNING'}else{'STOPPED'}\nGet-Content \"$rt\\solve.out\" -Tail 3 -ErrorAction SilentlyContinue")
  if 'STOPPED' in result:break
  assert time.monotonic()-start<3600,'Solve exceeded expected horizon, inspect; not killed'
  time.sleep(15)
 status('Collecting '+name);subprocess.run(['python3',str(N),'collect',name],check=True)
 status('Validating '+name);subprocess.run([sys.executable,str(T/'control/verify_transient.py'),name],check=True)
 checkpause()
status('All three native time histories accepted; expansion and rendering remain')

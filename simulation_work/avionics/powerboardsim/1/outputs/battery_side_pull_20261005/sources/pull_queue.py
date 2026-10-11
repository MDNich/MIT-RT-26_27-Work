from pull_paths import *
import sys,subprocess,time,json,datetime
cases=sys.argv[1:];log=S/'audit/queue.json'
def run(*args):
 p=subprocess.run(['python3',*args],text=True,capture_output=True)
 print(p.stdout[-4000:],p.stderr[-3000:],flush=True)
 if p.returncode:raise RuntimeError('Stage failed: '+' '.join(args))
def busy():
 p=subprocess.run(['python3','/tmp/powerboard_vm.py'],input="if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){'BUSY'}else{'IDLE'}",text=True,capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr)
 return 'BUSY' in p.stdout
for case in cases:
 D=S/'runtime'/case
 log.write_text(json.dumps(dict(case=case,status='waiting/preparing',time=datetime.datetime.now().isoformat()),indent=2))
 if not (D/'SOLVE_STARTED.txt').exists():
  assert not busy()
  
  if not (D/'PREFLIGHT_PASSED.txt').exists():run('/tmp/pull_native.py',case,'preflight')
  run('/tmp/pull_native.py',case,'solve')
 log.write_text(json.dumps(dict(case=case,status='solving',time=datetime.datetime.now().isoformat()),indent=2))
 while busy():time.sleep(15)
 run('/tmp/pull_native.py',case,'collect')
  # Do not attempt field extraction after a stopped or failed native solve.
 runout=(D/'run.out').read_text(errors='replace')
 import re
 if not re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',runout):raise RuntimeError('Native solve did not finish without errors: '+case)
 run('/tmp/pull_post.py',case);run('/tmp/pull_audit.py',case)
 log.write_text(json.dumps(dict(case=case,status='accepted',time=datetime.datetime.now().isoformat()),indent=2))
 print('ACCEPTED',case,flush=True)
 if (S/'audit/QUEUE_PAUSE').exists():
  print('QUEUE PAUSED between completed cases',flush=True);sys.exit(0)
log.write_text(json.dumps(dict(cases=cases,status='complete',time=datetime.datetime.now().isoformat()),indent=2))

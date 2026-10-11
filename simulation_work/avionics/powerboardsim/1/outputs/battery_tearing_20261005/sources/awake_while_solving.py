"""Read-only lifetime guard for caffeinate; never starts/stops a solver."""
from pathlib import Path
import sys,subprocess,json,time,datetime,os
S=Path(__file__).resolve().parent.parent
case=sys.argv[1];D=S/'runtime'/case
assert (D/'SOLVE_STARTED.json').exists()
rt='C:\\Temp\\PBTear26_'+case
log=S/'audit'/f'{case}_awake_guard.json'
start=time.monotonic()
state=dict(case=case,pid=os.getpid(),started=datetime.datetime.now().astimezone().isoformat(),purpose='Prevent idle system sleep while this existing solve runs; display sleep allowed. No solver mutations.',max_hours=6)
# Only scoped lock plus completed native footer ends the assertion early.
while time.monotonic()-start<6*3600:
 command=f"$active=Test-Path '{rt}\\tear.lock'; $complete=$false; if(Test-Path '{rt}\\run.out') {{$tail=Get-Content '{rt}\\run.out' -Tail 80; $complete=[bool]($tail -match 'Elapsed Time \\(sec\\)')}}; [PSCustomObject]@{{active=$active;complete=$complete}} | ConvertTo-Json -Compress"
 try:
  r=subprocess.run([sys.executable,str(S/'sources/vm_ps.py')],input=command,text=True,capture_output=True,timeout=55)
  if r.returncode:raise RuntimeError(r.stderr[-400:])
  status=json.loads(r.stdout.strip());state.update(last_check=datetime.datetime.now().astimezone().isoformat(),status=status)
  log.write_text(json.dumps(state,indent=2))
  if not status['active'] and status['complete']:
   state.update(ended=datetime.datetime.now().astimezone().isoformat(),reason='Native solve exited normally or with recorded failure; no lock remains.');log.write_text(json.dumps(state,indent=2));break
 except Exception as e:
  state.update(last_check=datetime.datetime.now().astimezone().isoformat(),read_error=str(e));log.write_text(json.dumps(state,indent=2))
 time.sleep(60)
else:
 state.update(ended=datetime.datetime.now().astimezone().isoformat(),reason='Six-hour assertion limit; solver untouched.');log.write_text(json.dumps(state,indent=2))

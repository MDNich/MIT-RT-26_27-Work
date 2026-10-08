from pathlib import Path
import subprocess,time,re,json,datetime,sys
T=Path(__file__).resolve().parents[1];P=T.parents[1];V=P/'outputs/video_4k60_20261005_1928/control/vm.py';C=T/'control'
assert '--run-authorized' in sys.argv

def vm(ps):
 r=subprocess.run(['python3',str(V)],input=ps,text=True,capture_output=True);r.check_returncode();return r.stdout

def win(p):return '\\\\Mac\\Home\\'+str(p).split('/Users/mdn/',1)[1].replace('/','\\')

def stamp(s):
 print(datetime.datetime.now().isoformat(),s,flush=True);(T/'pipeline_status.txt').write_text(datetime.datetime.now().isoformat()+' '+s)
try:
 stamp('Waiting for base vectors and modal expansion to complete')
 deadline=time.monotonic()+2700
 while True:
  z=vm("$s=Get-Content 'C:\\Temp\\PBMotion_20261005_basis\\solve.out' -Raw; if($s -match 'RUN COMPLETED'){Write-Output 'COMPLETE'}; if($s -match '\\*\\*\\* ERROR'){Write-Output 'ERROR'}; if(-not (Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue)){Write-Output 'IDLE'}")
  if 'ERROR' in z:raise RuntimeError('Basis reported ERROR; inspect, do not restart automatically.')
  if 'COMPLETE' in z and 'IDLE' in z:break
  if time.monotonic()>deadline:raise TimeoutError('Basis did not finish within inspection deadline; solver left untouched')
  time.sleep(20)
 vm("Invoke-Expression ([System.IO.File]::ReadAllText('"+win(C/'collect_basis.ps1')+"'))")
 s=(T/'basis/solve.out').read_text();assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',s);assert 'NUMBER OF STATIC SHAPES =      3' in s
 (T/'basis/ACCEPTED.json').write_text(json.dumps({'finished':datetime.datetime.now().isoformat(),'errors':0,'enforced_static_shapes':3,'source_mode_count':38,'ranks':12,'warnings':'Preserved in solve.out and file*.err; original model shape-testing and material-628 warnings.'},indent=2))
 stamp('Basis accepted; staging native transient pilot')
 subprocess.run(['python3',str(C/'native.py'),'stage','pilot_X_32768'],check=True)
 out=T/'pilot_X_32768/preflight.out';deadline=time.monotonic()+300
 while not out.exists():
  if time.monotonic()>deadline:raise TimeoutError('Pilot preflight not available')
  time.sleep(5)
 s=out.read_text();assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',s),s[-3000:]
 stamp('Transient pilot preflight passed; starting authorized 0.25 second pilot')
 subprocess.run(['python3',str(C/'native.py'),'run','pilot_X_32768'],check=True)
 stamp('Transient pilot running')
except Exception as e:
 stamp('STOPPED for inspection: '+repr(e));raise

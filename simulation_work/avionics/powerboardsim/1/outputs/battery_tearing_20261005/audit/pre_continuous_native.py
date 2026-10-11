from pathlib import Path
import subprocess,sys,json,hashlib,re,datetime
S=Path(__file__).resolve().parent.parent
case,action=sys.argv[1:3];D=S/'runtime'/case
runtime='C:\\Temp\\PBTear26_'+case
exe=r'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
def win(p):return 'Z:'+str(p).removeprefix('/Users/mdn').replace('/','\\')
def ps(s):
 r=subprocess.run([sys.executable,str(S/'sources/vm_ps.py')],input=s,text=True,capture_output=True,timeout=55)
 print(r.stdout,flush=True)
 if r.returncode:raise RuntimeError(r.stderr)
 return r.stdout
mf=json.loads((D/'input_sha256.json').read_text())
for f,h in mf.items():assert hashlib.sha256((D/f).read_bytes()).hexdigest()==h,f
cfg=json.loads((D/'config.json').read_text())
guard="if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'A MAPDL solver is already active'}\n"
if action=='preflight':
 license_text=ps("& 'C:\\Program Files\\ANSYS Inc\\v261\\licensingclient\\winx64\\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25")
 assert re.search(r'Total of 0 licenses? in use',license_text),'PrepPost license occupied; no preflight launched'
 guard=f"if(Test-Path '{runtime}\\check.lock'){{throw 'This preflight runtime is active'}}\n"
 assert not (D/'PREFLIGHT_STARTED.json').exists()
 ps(guard+f"New-Item -ItemType Directory -Path '{runtime}' -ErrorAction Stop | Out-Null\nCopy-Item '{win(D)}\\preflight.dat','{win(D)}\\run.dat' '{runtime}'")
 out=ps(guard+f"$p=Start-Process '{exe}' -ArgumentList '-b nolist -s noread -smp -np 1 -p preppost -j check -i preflight.dat -o preflight.out' -WorkingDirectory '{runtime}' -PassThru\n$p.Id")
 (D/'PREFLIGHT_STARTED.json').write_text(json.dumps(dict(pid=out.strip(),time=datetime.datetime.now().isoformat())))
elif action=='check':
 guard=f"if(Test-Path '{runtime}\\check.lock'){{throw 'This preflight runtime is active'}}\n"
 ps(guard+f"Copy-Item '{runtime}\\preflight.out','{runtime}\\check.err','{runtime}\\inventory.txt' '{win(D)}' -ErrorAction Stop")
 t=(D/'preflight.out').read_text(errors='replace')
 assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',t),'Preflight errors'
 inv=[int(float(x)) for x in (D/'inventory.txt').read_text().split()]
 assert inv==[cfg['nodes'],cfg['elements']],inv
 (D/'PREFLIGHT_PASSED.txt').write_text(mf['run.dat'])
 print('Native no-SOLVE preflight accepted',inv)
elif action=='solve':
 assert not (S/'audit/structural_license_hold.json').exists(),'Structural license is reserved for PCB Sim: Vibes after the current solve; coordinate before launch'
 video=S.parent/'video_4k60_20261005_1928'
 assert (video/'ALL_COMPLETE.txt').exists() or (S/'audit/exports_finished.json').exists(),'User requested waiting until video exports finish'
 assert (D/'PREFLIGHT_PASSED.txt').read_text()==mf['run.dat']
 assert not (D/'SOLVE_STARTED.json').exists()
 ranks=cfg.get('solver_ranks',4)
 # The structural seat serializes solves; independent PrepPost may remain active.
 guard=f"if(Test-Path '{runtime}\\tear.lock'){{throw 'This runtime has a solver lock'}}\n"
 license_text=ps("& 'C:\\Program Files\\ANSYS Inc\\v261\\licensingclient\\winx64\\lmutil.exe' lmstat -f ansys -c 1055@MARCDNICHITBF25")
 assert re.search(r'Total of 0 licenses? in use',license_text),'Structural license is occupied; no solve launched'
 out=ps(guard+f"if((Get-FileHash '{runtime}\\run.dat').Hash.ToLower() -ne '{mf['run.dat']}'){{throw 'Runtime hash changed'}}\n$p=Start-Process '{exe}' -ArgumentList '-b nolist -s noread -smp -np {ranks} -p ansys -j tear -i run.dat -o run.out' -WorkingDirectory '{runtime}' -PassThru\n$p.Id")
 (D/'SOLVE_STARTED.json').write_text(json.dumps(dict(pid=out.strip(),ranks=ranks,time=datetime.datetime.now().isoformat())))
elif action=='status':
 ps(f"Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue | Select-Object Name,Id,CPU\nif(Test-Path '{runtime}\\run.out'){{Get-Content '{runtime}\\run.out' -Tail 18}}else{{Get-Content '{runtime}\\preflight.out' -Tail 12}}")
elif action=='collect':
 guard=f"if(Test-Path '{runtime}\\tear.lock'){{throw 'This solver runtime is active'}}\n"
 ps(guard+f"Get-ChildItem '{runtime}' -File | Where-Object {{$_.Extension -in '.out','.err','.csv','.txt','.db','.log'}} | Copy-Item -Destination '{win(D)}'")
 t=(D/'run.out').read_text(errors='replace')
 print(re.findall(r'NUMBER OF.*MESSAGES ENCOUNTERED=.*',t))
 print((D/'history.csv').read_text()[-1800:] if (D/'history.csv').exists() else 'NO HISTORY')
else:raise ValueError(action)

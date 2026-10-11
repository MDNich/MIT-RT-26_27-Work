from pull_paths import *
import sys,json,hashlib,subprocess,re,datetime
case,action=sys.argv[1:3];D=S/'runtime'/case;runtime='C:\\Temp\\PBpull_'+case
mf=json.loads((D/'input_sha256.json').read_text())
for f,h in mf.items():assert hashlib.sha256((D/f).read_bytes()).hexdigest()==h

def ps(s):
 z=subprocess.run(['python3','/tmp/powerboard_vm.py'],input=s,text=True,capture_output=True);print(z.stdout,z.stderr,flush=True);z.check_returncode()
base="if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver already running'}\n"
exe=r'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe'
if action=='preflight':
 assert not (D/'SOLVE_STARTED.txt').exists()
 ps(base+f"New-Item -ItemType Directory -Path '{runtime}' -ErrorAction Stop | Out-Null\nCopy-Item '{win(D)}\\preflight.dat','{win(D)}\\run.dat' '{runtime}'")
 ps(f"$p=Start-Process '{exe}' -ArgumentList '-b nolist -s noread -smp -np 1 -p preppost -j check -i preflight.dat -o preflight.out' -WorkingDirectory '{runtime}' -PassThru -Wait\n$p.ExitCode")
 ps(f"Copy-Item '{runtime}\\preflight.out','{runtime}\\check.err','{runtime}\\inventory.txt' '{win(D)}'")
 t=(D/'preflight.out').read_text(errors='replace');assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',t)
 cfg=json.loads((D/'config.json').read_text());inv=[int(float(x)) for x in (D/'inventory.txt').read_text().split()]
 assert inv==[cfg['nodes'],cfg.get('expected_total_elements',cfg['shell_elements']+cfg['rigid_links'])],inv
 (D/'PREFLIGHT_PASSED.txt').write_text(mf['run.dat'])
elif action=='solve':
 assert (D/'PREFLIGHT_PASSED.txt').read_text()==mf['run.dat'];assert not (D/'SOLVE_STARTED.txt').exists()
 ps(base+f"if((Get-FileHash '{runtime}\\run.dat').Hash.ToLower() -ne '{mf['run.dat']}'){{throw 'Input changed'}}\n$p=Start-Process '{exe}' -ArgumentList '-b nolist -s noread -smp -np 4 -p ansys -j pull -i run.dat -o run.out' -WorkingDirectory '{runtime}' -PassThru\n$p.Id")
 (D/'SOLVE_STARTED.txt').write_text(datetime.datetime.now().isoformat())
elif action=='status':
 ps(f"Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue | Select-Object Name,Id,CPU\nGet-Content '{runtime}\\run.out' -Tail 24")
elif action=='collect':
 ps(base+f"Get-ChildItem '{runtime}' -File | Where-Object {{ $_.Extension -in '.out','.err','.csv','.txt','.rst','.db','.log' }} | Copy-Item -Destination '{win(D)}'")
 t=(D/'run.out').read_text(errors='replace');print(re.findall(r'NUMBER OF.*MESSAGES ENCOUNTERED=.*',t));print((D/'history.csv').read_text()[-1500:] if (D/'history.csv').exists() else 'NO HISTORY')

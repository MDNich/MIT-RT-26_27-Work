from pathlib import Path
import re,json,hashlib,subprocess,datetime
T=Path(__file__).resolve().parents[1];P=T.parents[1];B=T/'basis';m=json.loads((B/'manifest.json').read_text());out=(B/'preflight.out').read_text();assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',out);assert 'PREFLIGHT_MODE_RANGE=485.964268 TO 3986.07476' in out
assert not (B/'SOLVE_STARTED.txt').exists();h=hashlib.sha256((B/'run.dat').read_bytes()).hexdigest();assert h==m['run_sha256'];(B/'PREFLIGHT_PASSED.txt').write_text(h)
ps="""$ErrorActionPreference='Stop'
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver already active'}
if((Get-FileHash 'RUNTIME\\run.dat' -Algorithm SHA256).Hash.ToLower() -ne 'HASH'){throw 'Input changed'}
$p=Start-Process 'C:\\Program Files\\ANSYS Inc\\v261\\ansys\\bin\\winx64\\ANSYS261.exe' -ArgumentList '-b nolist -s noread -dis -np 12 -p ansys -j file -i run.dat -o solve.out' -WorkingDirectory 'RUNTIME' -PassThru
$p.Id
""".replace('RUNTIME',m['runtime']).replace('HASH',h)
(B/'SOLVE_STARTED.txt').write_text(datetime.datetime.now().isoformat());z=subprocess.run(['python3',str(P/'outputs/video_4k60_20261005_1928/control/vm.py')],input=ps,text=True,capture_output=True);print(z.stdout,z.stderr);(B/'launch_log.txt').write_text(z.stdout+z.stderr);z.check_returncode()

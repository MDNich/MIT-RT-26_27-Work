from rv_paths import *
import sys,json,hashlib,subprocess,datetime
axis=sys.argv[1];variant=('_'+sys.argv[2]) if len(sys.argv)>2 else '';C=R/axis/('local_recovery'+variant);runtime=(C/'runtime.txt').read_text();mf=json.loads((C/'manifest.json').read_text())
assert (C/'PREFLIGHT_PASSED.txt').read_text()==hashlib.sha256((C/'run.dat').read_bytes()).hexdigest()==mf['run_sha256']
assert not (C/'SOLVE_STARTED.txt').exists()
ps=r'''
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver process exists'}
$hash=(Get-FileHash 'RUNTIME\run.dat' -Algorithm SHA256).Hash.ToLower()
if($hash -ne 'HASH'){throw 'Local native input does not match preflight'}
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -s noread -dis -np 12 -p ansys -j file -i run.dat -o solve.out' -WorkingDirectory 'RUNTIME' -PassThru
$p.Id
'''.replace('RUNTIME',runtime).replace('HASH',mf['run_sha256'])
(C/'SOLVE_STARTED.txt').write_text(datetime.datetime.now().isoformat())
z=subprocess.run(['python3','/tmp/powerboard_vm.py'],input=ps,text=True,capture_output=True);print(z.stdout,z.stderr);z.check_returncode()
(C/'launcher.txt').write_text(z.stdout)

from pathlib import Path
import sys,json,subprocess,hashlib,re,datetime
T=Path(__file__).resolve().parents[1];P=T.parents[1];V=P/'outputs/video_4k60_20261005_1928/control/vm.py'
mode,name=sys.argv[1:];O=T/name;m=json.loads((O/'manifest.json').read_text());rt=m['runtime']
def win(p):return '\\\\Mac\\Home\\'+str(p).split('/Users/mdn/',1)[1].replace('/','\\')
def vm(ps):
 z=subprocess.run(['python3',str(V)],input=ps,text=True,capture_output=True);print(z.stdout);print(z.stderr,file=sys.stderr);z.check_returncode();return z.stdout
if mode=='stage':
 assert (T/'basis/ACCEPTED.json').exists()
 if 'source' in m:
  assert (T/m['source']/'ACCEPTED.json').exists()
  assert (T/'basis_aux_smp/ACCEPTED.json').exists()
 if m.get('parallel_mode')=='smp':assert (T/'basis_smp/ACCEPTED.json').exists()
 path=win(T/'control'/('stage_'+name+'.ps1'))
 vm("$p=Start-Process powershell.exe -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \""+path+"\"' -PassThru\n$p.Id")
elif mode=='run':
 assert not (O/'SOLVE_STARTED.txt').exists()
 out=(O/'preflight.out').read_text();assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',out)
 assert re.search(r'NUMBER OF WARNING\s+MESSAGES ENCOUNTERED=\s*0',out)
 h=hashlib.sha256((O/'run.dat').read_bytes()).hexdigest();assert h==m['run_sha256'];(O/'PREFLIGHT_PASSED.txt').write_text(h)
 ps="""$ErrorActionPreference='Stop'
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver already active'}
if((Get-FileHash 'RUNTIME\\run.dat').Hash.ToLower() -ne 'HASH'){throw 'Input mismatch'}
ACC_CHECK
$p=Start-Process 'C:\\Program Files\\ANSYS Inc\\v261\\ansys\\bin\\winx64\\ANSYS261.exe' -ArgumentList '-b nolist -s noread PARALLEL -p ansys -j file -i run.dat -o solve.out' -WorkingDirectory 'RUNTIME' -PassThru
$p.Id
""".replace('ACC_CHECK', "if((Get-FileHash 'RUNTIME\\acc.txt').Hash.ToLower() -ne '"+m['input_sha256']+"'){throw 'Acceleration mismatch'}" if 'input_sha256' in m else '').replace('RUNTIME',rt).replace('HASH',h).replace('PARALLEL', '-smp -np 1' if m.get('parallel_mode')=='smp' else '-dis -np 12')
 (O/'SOLVE_STARTED.txt').write_text(datetime.datetime.now().isoformat());(O/'launch_log.txt').write_text(vm(ps))
elif mode=='collect':
 vm("Copy-Item '"+rt+"\\solve.out','"+rt+"\\file*.err','"+rt+"\\file.mcf' '"+win(O)+"'")
else:raise ValueError(mode)

from rv_paths import *
import sys,subprocess,json,re,hashlib,datetime
axis=sys.argv[1];variant=('_'+sys.argv[2]) if len(sys.argv)>2 else '';C=R/axis/('local_recovery'+variant)
runtime=(C/'runtime.txt').read_text();dest=win(C)
ps=r'''
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver processes still running'}
$s=Get-Content 'RUNTIME\solve.out' -Raw
if($s -notmatch 'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0' -or $s -notmatch 'RUN COMPLETED'){throw 'Native solve not verified'}
Copy-Item 'RUNTIME\solve.out','RUNTIME\run.dat','RUNTIME\file0.err','RUNTIME\file.db','RUNTIME\file.rst','RUNTIME\file.psd' 'DEST'
'''.replace('RUNTIME',runtime).replace('DEST',dest)
z=subprocess.run(['python3','/tmp/powerboard_vm.py'],input=ps,text=True,capture_output=True);print(z.stdout,z.stderr);z.check_returncode()
s=(C/'solve.out').read_text(errors='replace')
assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',s)
assert all(v in s for v in ['DISPLACEMENT-TYPE','VELOCITY-TYPE','ACCELERATION-TYPE'])
assert 'ALL MODES FROM THE MODAL ANALYSIS ARE SELECTED FOR COMBINATION.' in s
assert re.search(r'DAMPING RATIO\s*=\s*0.0200',s)
assert len(re.findall('FIXED RELATIVE MOTION=',s))>=6
# Accepted binaries are outside Mechanical's generated-data directories.
manifest={'axis':axis,'runtime':runtime,'errors':0,'warnings':int(re.search(r'NUMBER OF WARNING\s+MESSAGES ENCOUNTERED=\s*(\d+)',s)[1]),'damping_ratio':.02,'all_38_modes':True,'six_locked_pretensions':True,'files':{}}
for name in ['run.dat','solve.out','file.rst','file.db','file.psd']:
 f=C/name
 with f.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
 manifest['files'][name]={'bytes':f.stat().st_size,'sha256':digest}
(C/'native_solver_audit.json').write_text(json.dumps(manifest,indent=2))
(C/'NATIVE_SOLVED.txt').write_text(datetime.datetime.now().isoformat())
(R/axis/'accepted_native_directory.txt').write_text(str(C))
print(axis,'native solve accepted and archived',flush=True)

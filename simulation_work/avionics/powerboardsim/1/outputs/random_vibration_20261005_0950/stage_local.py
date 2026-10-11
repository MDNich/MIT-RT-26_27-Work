from rv_paths import *
import sys,subprocess,re,json,hashlib
axis=sys.argv[1];assert axis in ['X','Y','Z']
variant=('_'+sys.argv[2]) if len(sys.argv)>2 else ''
C=R/axis/('local_recovery'+variant);C.mkdir(exist_ok=True)
source=P/'powerboardsim_v1_files/dp0/SYS-4/MECH'
runtime='C:\\Temp\\PCBRV_20261005_'+axis+'_local'+variant
assert not (C/'SOLVE_STARTED.txt').exists()
s=(R/axis/'psd_input.dat').read_text()
# Change only Workbench bookkeeping directory strings; physics commands remain unchanged.
for src in re.findall(r"'(Z:\\[^']+\\)'",s):
 if 'SYS-' in src:s=s.replace(src,runtime+'\\')
(C/'run.dat').write_text(s)
pre=(R/axis/'preflight.dat').read_text()
pre=re.sub(r"(?im)^resume,.*?,db$",'resume,file,db',pre)
(C/'preflight.dat').write_text(pre)
(C/'runtime.txt').write_text(runtime)
manifest={'axis':axis,'runtime':runtime,'mode':'12 distributed ranks, same as modal basis','source':str(source),'run_sha256':hashlib.sha256(s.encode()).hexdigest(),'reason':'Mechanical returned a generic result-import failure although MAPDL completed with zero errors. The subsequent by-reference import cleared X working files. Recompute in an isolated local folder; preserve results before any UI import.','source_files':{f.name:f.stat().st_size for f in source.iterdir() if re.fullmatch(r'file\d*\.(db|mode|full|esav|emat|rst)',f.name,re.I) or f.name=='file.DSP'}}
(C/'manifest.json').write_text(json.dumps(manifest,indent=2))
ps=r'''
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver process exists'}
New-Item -ItemType Directory -Path 'RUNTIME' -ErrorAction Stop | Out-Null
Get-ChildItem 'SOURCE' -File | Where-Object { $_.Name -match '^file\d*\.(db|mode|full|esav|emat|rst)$' -or $_.Name -eq 'file.DSP' } | Copy-Item -Destination 'RUNTIME'
Copy-Item 'WIN\run.dat','WIN\preflight.dat' 'RUNTIME'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j psdcheck -i preflight.dat -o preflight.out' -WorkingDirectory 'RUNTIME' -PassThru -Wait
Copy-Item 'RUNTIME\preflight.out','RUNTIME\psdcheck.err','RUNTIME\excitation_nodes.txt' 'WIN'
Write-Output ('Local preflight exit '+$p.ExitCode)
'''.replace('RUNTIME',runtime).replace('SOURCE',win(source)).replace('WIN',win(C))
# Keep each interactive Parallels command below the guest argument-length limit.
steps=[ps[:ps.index("$p=Start-Process")],ps[ps.index("$p=Start-Process"):ps.index("Copy-Item '"+runtime+"\\preflight.out'")],ps[ps.index("Copy-Item '"+runtime+"\\preflight.out'"):]]
for step in steps:
 z=subprocess.run(['python3','/tmp/powerboard_vm.py'],input=step,text=True,capture_output=True)
 print(z.stdout,z.stderr,flush=True);z.check_returncode()
out=(C/'preflight.out').read_text(errors='replace')
assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',out)
assert {int(float(v)) for v in (C/'excitation_nodes.txt').read_text().split()}=={int(v) for v in (R/'mounting_nodes.txt').read_text().split()}
(C/'PREFLIGHT_PASSED.txt').write_text(manifest['run_sha256'])
print(axis,'local preflight passed',flush=True)

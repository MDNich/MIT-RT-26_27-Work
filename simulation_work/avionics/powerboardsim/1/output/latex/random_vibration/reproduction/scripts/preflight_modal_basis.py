from pathlib import Path
import re,hashlib,json,datetime,subprocess
P=Path('/Users/mdn/Developer/MIT_Rkt_Team/2026-7/MIT-RT-26_27-Work/simulation_work/avionics/powerboardsim/1');R=Path((P/'outputs/bolt_manager_work/latest_resume.txt').read_text().strip());C=P/'outputs/random_vibration_20261005_0950/modal_basis';S=C/'modal_input.dat';s=S.read_text()
assert (R/'bolted750_refined/STATIC_VERIFIED.txt').exists()
assert 'antype,,restart,,,perturbation' in s.lower()
assert 'perturb,modal,,CURRENT,DZEROKEEP' in s
assert re.search(r'modopt,lanb,60,1\.,4000\.',s,re.I)
assert not re.search(r'^\s*(?:psmesh|nblock|eblock|et,)',s,re.M|re.I)
assert s.count('*IF,PBAnalysis,EQ,0,THEN')==6
assert len(re.findall(r'^solve(?:\s*,\s*elform\b|\s*$)',s,re.M|re.I))==2
base=P/'powerboardsim_v1_files/dp0/SYS-2/MECH'
winbase='Z:'+str(base).removeprefix('/Users/mdn').replace('/','\\')
start=s.index('!APDL Bolt Assembly object: 4139');end=s.index('\nsolve\n',start)
pre="/BATCH\nRESUME,'%s\\file',rdb\n/SOLU\nANTYPE,MODAL\nMODOPT,LANB,60,1.,4000.\n"%winbase+s[start:end]+'''
*GET,PBCheckAnty,ACTIVE,0,ANTY
/COM,PREFLIGHT_MODAL_ANTY=%PBCheckAnty%
*IF,PBCheckAnty,NE,2,THEN
*MSG,FATAL
Expected modal analysis type 2.
*ENDIF
FINISH
/PREP7
ALLSEL,ALL
*GET,PBNC,NODE,0,COUNT
*GET,PBEC,ELEM,0,COUNT
/COM,PREFLIGHT_INHERITED_NODES=%PBNC% ELEMENTS=%PBEC%
*CFOPEN,modal_parent_inventory,csv
*VWRITE
('bolt,pilot,pretension_elements')
*DO,PBI,1,6
PBN=PBPilot%PBI%
PBS=PBSection%PBI%
ESEL,S,TYPE,,PBS
*GET,PBC,ELEM,0,COUNT
*IF,PBC,LT,1,THEN
*MSG,FATAL
Missing inherited pretension elements.
*ENDIF
*VWRITE,PBI,PBN,PBC
(F3.0,',',F10.0,',',F10.0)
*ENDDO
*CFCLOS
ALLSEL,ALL
/COM,PRESTRESS_PARENT_AND_MODAL_GUARDS_VERIFIED
FINISH
/EXIT,NOSAVE
'''
assert not re.search(r'^\s*solve\b',pre,re.M|re.I)
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S');F=C/('preflight_'+stamp);F.mkdir();(F/'preflight.dat').write_text(pre)
files=[S,R/'bolted750_refined/ds.dat',base/'file.rdb',base/'file.ldhi']
(F/'input_manifest.json').write_text(json.dumps({'purpose':'No SOLVE; read converged parent model database, verify six existing pretension sections, modal settings and static-only load guards. Final locked forces verified separately from static result. Full perturbation matrices are formed only during the authorized modal solve.','files':{str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in files}},indent=2))
win='Z:'+str(F).removeprefix('/Users/mdn').replace('/','\\');runtime='C:\\Temp\\PCBRV_modalcheck_'+stamp
ps=r'''
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver process exists'}
New-Item -ItemType Directory -Path 'RUNTIME' -ErrorAction Stop | Out-Null
Copy-Item 'WIN\preflight.dat' 'RUNTIME\preflight.dat'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j modalcheck -i preflight.dat -o preflight.out' -WorkingDirectory 'RUNTIME' -PassThru
$p.Id
'''.replace('RUNTIME',runtime).replace('WIN',win)
z=subprocess.run(['python3','/tmp/powerboard_vm.py'],input=ps,text=True,capture_output=True);print(z.stdout,z.stderr);z.check_returncode();(C/'preflight_runtime.txt').write_text(runtime);(C/'preflight_source_dir.txt').write_text(str(F));print(runtime)

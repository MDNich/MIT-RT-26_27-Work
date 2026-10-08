from rv_paths import *
import re,json,hashlib,datetime,subprocess
assert (R/'modal_basis/audit.json').exists()
base=P/'powerboardsim_v1_files/dp0/SYS-4/MECH'
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
for axis in ['X','Y','Z']:
 C=R/axis;s=(C/'psd_input.dat').read_text()
 assert re.search('(?im)^dmprat,2.e-002',s)
 assert re.search('(?im)^spopt,psd,,yes',s)
 assert re.search('(?im)^psdcom,0.00',s)
 assert re.search('(?im)^PSDUNIT,1,ACEL$',s)
 assert re.search('(?im)^PSDFRQ,1,,20.,50.,800.,2000.$',s)
 expected=[.026,.16,.16,.026]
 vals=[float(v) for v in re.search(r'(?im)^PSDVAL,1,(.*)$',s)[1].split(',')]
 assert all(abs(x/(9.80665**2)-e)<1e-11 for x,e in zip(vals,expected))
 assert ('d,all,u'+axis.lower()+',1') in s.lower()
 assert len(re.findall(r'(?im)^pfact,1,base',s))==1
 assert not re.search(r'(?im)^\s*(nblock|eblock|psmesh)\b',s)
 assert s.count('*IF,PBAnalysis,EQ,0,THEN')==12
 pre=s[:s.lower().index('pfact,1,base')]
 pre=pre.replace('resume,file,db',"resume,'%s\\file',db"%win(base))
 pre+='''
*GET,PBCheckAnty,ACTIVE,0,ANTY
/COM,PREFLIGHT_PSD_ANTY=%PBCheckAnty%
*IF,PBCheckAnty,NE,8,THEN
*MSG,FATAL
Expected spectrum analysis type 8.
*ENDIF
NSEL,S,D,UAXIS,1
*GET,PBCount,NODE,0,COUNT
/COM,PREFLIGHT_EXCITATION_NODES=%PBCount%
*IF,PBCount,NE,781,THEN
*MSG,FATAL
Unexpected excitation-node count.
*ENDIF
*DIM,PBExcNodes,ARRAY,PBCount
*VGET,PBExcNodes(1),NODE,,NLIST
*CFOPEN,excitation_nodes,txt
*VWRITE,PBExcNodes(1)
(F12.0)
*CFCLOS
ALLSEL,ALL
SPTOPT
STAT
/SHOW,PNG
/GFILE,1200
PSDGRAPH,1,1,0
/SHOW,CLOSE
FINISH
/PREP7
*GET,PBNC,NODE,0,COUNT
*GET,PBEC,ELEM,0,COUNT
/COM,PREFLIGHT_MODEL_NODES=%PBNC% ELEMENTS=%PBEC%
/COM,PSD_INPUT_AND_EXCITATION_SCOPING_VERIFIED
FINISH
/EXIT,NOSAVE
'''.replace('UAXIS','U'+axis)
 assert not re.search(r'(?im)^\s*(solve|pfact)\b',pre)
 C.joinpath('preflight.dat').write_text(pre)
 C.joinpath('input_manifest.json').write_text(json.dumps({'axis':axis,'sha256':hashlib.sha256(s.encode()).hexdigest(),'purpose':'Read complete modal database; parse spectrum and ACT guards; verify unit base-motion constraint scoped to the 781 mounting-face nodes; no PFACT or SOLVE.'},indent=2))
 runtime='C:\\Temp\\PCBRV_'+axis+'_preflight_'+stamp
 C.joinpath('preflight_runtime.txt').write_text(runtime)
 ps=r'''
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'An existing solver is running'}
New-Item -ItemType Directory -Path 'RUNTIME' -ErrorAction Stop | Out-Null
Copy-Item 'WIN\preflight.dat' 'RUNTIME\preflight.dat'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j psdcheck -i preflight.dat -o preflight.out' -WorkingDirectory 'RUNTIME' -PassThru -Wait
Copy-Item 'RUNTIME\preflight.out','RUNTIME\psdcheck.err','RUNTIME\excitation_nodes.txt' 'WIN'
Get-ChildItem 'RUNTIME\*.png' | Copy-Item -Destination 'WIN'
Write-Output ('AXIS preflight exited '+$p.ExitCode)
'''.replace('RUNTIME',runtime).replace('WIN',win(C)).replace('AXIS',axis)
 result=subprocess.run(['python3','/tmp/powerboard_vm.py'],input=ps,text=True,capture_output=True)
 print(result.stdout,result.stderr,flush=True);result.check_returncode()
 out=C.joinpath('preflight.out').read_text(errors='replace')
 assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',out)
 assert 'PSD_INPUT_AND_EXCITATION_SCOPING_VERIFIED' in out
 nodes={int(float(v)) for v in C.joinpath('excitation_nodes.txt').read_text().split()}
 expectednodes={int(v) for v in R.joinpath('mounting_nodes.txt').read_text().split()}
 assert nodes==expectednodes
 assert (C/'psd_input.dat').read_text()==s
 C.joinpath('PREFLIGHT_PASSED.txt').write_text(hashlib.sha256(s.encode()).hexdigest()+'\n781 excitation nodes match the eight physical mounting faces. Native errors: 0.\n')
 print(axis,'PASSED',flush=True)

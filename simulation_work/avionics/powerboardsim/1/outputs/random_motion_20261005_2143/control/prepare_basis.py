from pathlib import Path
import re,json,hashlib
T=Path(__file__).resolve().parents[1];P=T.parents[1];R=P/'outputs/random_vibration_20261005_0950'
B=T/'basis';B.mkdir(exist_ok=True)
def win(p):return '\\\\Mac\\Home\\'+str(p).split('/Users/mdn/',1)[1].replace('/','\\')
s=(R/'X/preflight.dat').read_text();cm=s[s.index('CMBLOCK,USERSELFSU'):s.index('cmsel,s,USERSELFSU')]
common='''/batch
resume,file,db
allsel,all
'''+cm+'''/solu
antype,modal,restart
fdele,all,all
acel,0,0,0
modcont,,on
mxpand,38,,,yes,,yes
cmsel,s,USERSELFSU
'''
check='''*get,PBNC,node,0,count
*if,PBNC,ne,781,then
*msg,fatal
Support node count mismatch.
*endif
'''
for dof in ['UX','UY','UZ']:
 check+='cmsel,s,USERSELFSU\nnsel,r,d,'+dof+',0\n*get,PBNF,node,0,count\n*if,PBNF,ne,781,then\n*msg,fatal\nSupport DOFs were not all blocked in source modal model.\n*endif\n'
base='cmsel,s,USERSELFSU\nd,all,ux,1\nd,all,uy,2\nd,all,uz,3\nallsel,all\n'
pre=common+check+base+'''*get,PBNC,node,0,count
*get,PBEC,elem,0,count
/com,PREFLIGHT_MODEL_NODES=%PBNC% ELEMENTS=%PBEC%
*get,PBF1,mode,1,freq
*get,PBF38,mode,38,freq
/com,PREFLIGHT_MODE_RANGE=%PBF1% TO %PBF38%
stat
finish
/exit,nosave
'''
run=common+check+base+'''outpr,all,none
solve
save,file,db
finish
/exit,nosave
'''
(B/'preflight.dat').write_text(pre);(B/'run.dat').write_text(run)
rt=r'C:\Temp\PBMotion_20261005_basis';source=P/'powerboardsim_v1_files/dp0/SYS-4/MECH'
m={'runtime':rt,'source':str(source),'ranks':12,'run_sha256':hashlib.sha256(run.encode()).hexdigest(),'preflight_sha256':hashlib.sha256(pre.encode()).hexdigest(),'purpose':'Add three enforced-base vectors in modal restart without eigenvalue recalculation; preserve archived source modal basis.'}
(B/'manifest.json').write_text(json.dumps(m,indent=2))
ps=r'''$ErrorActionPreference='Stop'
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver already active'}
New-Item -ItemType Directory -Path 'RUNTIME' -ErrorAction Stop | Out-Null
Get-ChildItem 'SOURCE' -File | Where-Object { $_.Name -match '^file\d*\.(db|mode|full|esav|emat)$' -or $_.Name -eq 'file.DSP' } | Copy-Item -Destination 'RUNTIME'
Copy-Item 'BASIS\run.dat','BASIS\preflight.dat' 'RUNTIME'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j check -i preflight.dat -o preflight.out' -WorkingDirectory 'RUNTIME' -PassThru -Wait
Copy-Item 'RUNTIME\preflight.out','RUNTIME\check.err' 'BASIS'
$p.ExitCode | Out-File 'BASIS\preflight_exit.txt'
'''.replace('RUNTIME',rt).replace('SOURCE',win(source)).replace('BASIS',win(B))
(T/'control/stage_basis.ps1').write_text(ps)
print(win(T/'control/stage_basis.ps1'))

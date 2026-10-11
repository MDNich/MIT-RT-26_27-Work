from pathlib import Path
import sys,hashlib,json
T=Path(__file__).resolve().parents[1]
smp="--smp" in sys.argv
name,axis,fs,duration=sys.argv[1:5];fs=int(fs);duration=float(duration);assert axis in 'XYZ';O=T/name;O.mkdir(exist_ok=True)
def win(p):return '\\\\Mac\\Home\\'+str(p).split('/Users/mdn/',1)[1].replace('/','\\')
rt='C:\\Temp\\PBMotion_20261005_'+name
common='''/batch
resume,file,db
allsel,all
finish
/solu
antype,trans
trnopt,msup,38,,1,yes,nmk,yes
mcfopt,1,0,0
dmprat,0.02
tintp,0,,,,,,,,1
kbc,1
outpr,all,none
outres,all,all
rescontrol,define,last,last
'''+f'deltim,{1/fs:.16g}\n'+'''dval,1,acc,0,,off
dval,2,acc,0,,off
dval,3,acc,0,,off
'''
load='''*dim,PBACC,table,589825,1,,time
*tread,PBACC,acc,txt
'''+f'dval,{"XYZ".index(axis)+1},acc,%PBACC%,,off\ntime,{duration}\n'
pre=common+load+'''*get,PBNC,node,0,count
*get,PBEC,elem,0,count
/com,PREFLIGHT_MODEL_NODES=%PBNC% ELEMENTS=%PBEC%
/com,PREFLIGHT_TIMEHISTORY_INPUT_LOADED
/com,INPUT_FIRST=%PBACC(1,1)% LAST=%PBACC(589825,1)%
finish
/exit,nosave
'''
run=common+'''solve
'''+load+'''solve
save,file,db
finish
/exit,nosave
'''
(O/'run.dat').write_text(run);(O/'preflight.dat').write_text(pre)
m={'name':name,'axis':axis,'fs_Hz':fs,'duration_s':duration,'ranks':(1 if smp else 12),'parallel_mode':('smp' if smp else 'dmp'),'runtime':rt,'run_sha256':hashlib.sha256(run.encode()).hexdigest(),'input_sha256':hashlib.sha256((T/'inputs'/(axis+'_acc.txt')).read_bytes()).hexdigest(),'relative_displacements':True,'enforced_base':"XYZ".index(axis)+1,'damping_ratio':.02}
(O/'manifest.json').write_text(json.dumps(m,indent=2))
ps=r'''$ErrorActionPreference='Stop'
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'PrepPost seat busy'}
New-Item -ItemType Directory -Path 'RUNTIME' -ErrorAction Stop | Out-Null
Get-ChildItem 'C:\Temp\PBMotion_20261005_basis' -File | Where-Object { $_.Name -match '^file\d*\.(db|mode|full|mlv|enf)$' } | Copy-Item -Destination 'RUNTIME'
Copy-Item 'OUT\run.dat','OUT\preflight.dat' 'RUNTIME'
Copy-Item 'INPUT' 'RUNTIME\acc.txt'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j file -i preflight.dat -o preflight.out' -WorkingDirectory 'RUNTIME' -PassThru -Wait
Copy-Item 'RUNTIME\preflight.out','RUNTIME\file.err' 'OUT'
$p.ExitCode | Out-File 'OUT\preflight_exit.txt'
'''.replace('RUNTIME',rt).replace('OUT',win(O)).replace('INPUT',win(T/'inputs'/(axis+'_acc.txt')))
if smp:
 ps=ps.replace('C:\\Temp\\PBMotion_20261005_basis', 'C:\\Temp\\PBMotion_20261005_basis_smp').replace('^file\\d*\\.(db|mode|full|mlv|enf)$','^file\\.(db|mode|full|mlv|enf)$')
(T/'control'/('stage_'+name+'.ps1')).write_text(ps);print(win(T/'control'/('stage_'+name+'.ps1')))

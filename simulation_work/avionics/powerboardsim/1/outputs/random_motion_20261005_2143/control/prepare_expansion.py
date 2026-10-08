from pathlib import Path
import sys,json,hashlib
T=Path(__file__).resolve().parents[1];R=T.parents[1]/'outputs/random_vibration_20261005_0950'
name,source,count,begin,spacing=sys.argv[1:6];count=int(count);begin=float(begin);spacing=float(spacing);stress='--stress' in sys.argv;O=T/name;O.mkdir(exist_ok=True);m=json.loads((T/source/'manifest.json').read_text());rt='C:\\Temp\\PBMotion_20261005_'+name
ids=[int(x) for x in (R/'pcb_elements.txt').read_text().split()];assert ids==list(range(min(ids),max(ids)+1)), 'Noncontiguous PCB elements need list selection'
common=f'''/batch
resume,file,db
/prep7
esel,s,elem,,{min(ids)},{max(ids)}
cm,PBVIDEO,elem
*get,PBEC,elem,0,count
/com,PCB_SELECTED_ELEMENTS=%PBEC%
allsel,all
finish
/solu
expass,on
numexp,{count},{begin:.16g},{begin+count*spacing:.16g},{'yes' if stress else 'no'}
outres,all,none
outres,nsol,all
'''
if stress:common+='outres,strs,all,PBVIDEO\n'
pre=common+'finish\n/exit,nosave\n';run=common+'solve\nfinish\n/post1\nset,list\nfinish\n/exit,nosave\n'
(O/'run.dat').write_text(run);(O/'preflight.dat').write_text(pre)
def win(p):return '\\\\Mac\\Home\\'+str(p).split('/Users/mdn/',1)[1].replace('/','\\')
manifest={'source':source,'axis':m['axis'],'runtime':rt,'source_runtime':m['runtime'],'result_sets':count,'first_time_s':begin+spacing,'last_time_s':begin+count*spacing,'frame_spacing_s':spacing,'stress_scoped_to_PCB':stress,'pcb_element_count':len(ids),'run_sha256':hashlib.sha256(run.encode()).hexdigest(),'parallel_mode':'smp','ranks':1}
(O/'manifest.json').write_text(json.dumps(manifest,indent=2))
ps=r'''$ErrorActionPreference='Stop'
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'PrepPost seat busy'}
New-Item -ItemType Directory -Path 'RUNTIME' -ErrorAction Stop | Out-Null
Get-ChildItem 'SOURCE' -File | Where-Object {$_.Name -match '^file\.(db|mode|full|mlv|enf|rdsp)$'} | Copy-Item -Destination 'RUNTIME'
Copy-Item 'C:\Temp\PBMotion_20261005_basis_aux_smp\file.emat','C:\Temp\PBMotion_20261005_basis_aux_smp\file.esav' 'RUNTIME'
Copy-Item 'OUT\run.dat','OUT\preflight.dat' 'RUNTIME'
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j file -i preflight.dat -o preflight.out' -WorkingDirectory 'RUNTIME' -PassThru -Wait
Copy-Item 'RUNTIME\preflight.out','RUNTIME\file.err' 'OUT'
$p.ExitCode | Out-File 'OUT\preflight_exit.txt'
'''.replace('RUNTIME',rt).replace('SOURCE',m['runtime']).replace('OUT',win(O))
(T/'control'/('stage_'+name+'.ps1')).write_text(ps)
print(json.dumps(manifest,indent=2))

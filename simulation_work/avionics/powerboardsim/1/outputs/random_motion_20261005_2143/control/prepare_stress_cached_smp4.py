from pathlib import Path
import numpy as np,json,hashlib
T=Path(__file__).resolve().parents[1];O=T/'stress_cached_smp4';O.mkdir(exist_ok=False);x=np.load(T/'transient_X/modal_coordinates.npy');times=[1+1/16384,1+4/16384];rows=[x[np.argmin(abs(x[:,0]-t))] for t in times];ns=[149869,173651]
lines=['/batch','resume,file,db','allsel,all','/post1','inres,nsol,strs','rsys,solu','esel,s,elem,,73331,112344','nsel,all']
for mode in range(1,39):lines.append(f'lcfile,{mode},shape{mode:02d},lcs')
lines+=['file,seed,rst','set,1,1','reswrite,seedout','*cfopen,combined_nodes,csv']
for i,row in enumerate(rows):
 lines+=['file,modes,rst','set,1,1','lcoper,zero']
 for j in range(1,39):lines.append(f'lcfact,{j},{row[j]:.16e}')
 lines+=['lcoper,add,all']
 for n in ns:
  for k,comp in enumerate(['X','Y','Z','XY','YZ','XZ']):
   lines += [f'*get,PBS,node,{n},S,{comp}',f'*vwrite,{i+1},{n},{k+1},PBS',"(F4.0,',',F9.0,',',F2.0,',',E24.16)"]
 if i==0:lines+=['file,seedout,rst',f'rappnd,2,{row[0]:.16e}','set,2,1','reswrite,motion']
 else:lines+=['file,motion,rst',f'rappnd,{i+2},{row[0]:.16e}']
lines+=['*cfclos','file,motion,rst','set,list','*cfopen,roundtrip_nodes,csv']
for i in range(2):
 lines.append(f'set,{i+2},1')
 for n in ns:
  for k,comp in enumerate(['X','Y','Z','XY','YZ','XZ']):
   lines += [f'*get,PBS,node,{n},S,{comp}',f'*vwrite,{i+1},{n},{k+1},PBS',"(F4.0,',',F9.0,',',F2.0,',',E24.16)"]
lines+=['*cfclos','finish','/exit,nosave'];s='\n'.join(lines)+'\n';(O/'run.dat').write_text(s)
m={'no_solve':True,'nodes':ns,'times_s':times,'q_source':'transient_X/modal_coordinates.npy','cached_modes_source':'C:/Temp/PBMotion_20261005_stress_lcproof_v3/shape*.lcs','input_sha256':hashlib.sha256(s.encode()).hexdigest(),'seed_excluded_from_final_motion_rst':True};(O/'manifest.json').write_text(json.dumps(m,indent=2))
win=lambda p:'\\\\Mac\\Home'+str(p).split('/Users/mdn',1)[1].replace('/','\\')
ps=r'''$ErrorActionPreference='Stop'
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver active'}
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f ansys -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'Seat busy'}
$rt='C:\Temp\PBMotion_20261005_stress_cached_smp4'
New-Item -ItemType Directory -Path $rt -ErrorAction Stop | Out-Null
$cache='C:\Temp\PBMotion_20261005_stress_lcproof_v3'
Copy-Item "$cache\file.db" $rt
foreach($n in @('modes.rst','seed.rst')){New-Item -ItemType HardLink -Path "$rt\$n" -Target "$cache\$n" | Out-Null}
$files=@(Get-ChildItem "$cache\shape*.lcs");if($files.Count -ne 38){throw 'Missing modal cache'}
foreach($f in $files){New-Item -ItemType HardLink -Path "$rt\$($f.Name)" -Target $f.FullName | Out-Null}
Copy-Item 'OUT\run.dat' $rt
if((Get-FileHash "$rt\run.dat").Hash.ToLower() -ne 'SHA'){throw 'Input mismatch'}
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 4 -p ansys -j file -i run.dat -o run.out' -WorkingDirectory $rt -PassThru -Wait
foreach($n in @('run.out','file.err','combined_nodes.csv','roundtrip_nodes.csv')){if(Test-Path "$rt\$n"){Copy-Item "$rt\$n" 'OUT'}}
$p.ExitCode | Out-File 'OUT\exit_code.txt'
'''.replace('OUT',win(O)).replace('SHA',m['input_sha256'])
(T/'control/stress_cached_smp4.ps1').write_text(ps)

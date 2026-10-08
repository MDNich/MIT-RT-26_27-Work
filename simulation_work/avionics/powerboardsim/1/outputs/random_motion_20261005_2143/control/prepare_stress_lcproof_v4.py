from pathlib import Path
import numpy as np,json,hashlib
T=Path(__file__).resolve().parents[1];P=T.parents[1];O=T/'stress_lcproof_v4';O.mkdir(exist_ok=True);R=P/'outputs/random_vibration_20261005_0950';nodes=np.loadtxt(R/'pcb_nodes.txt',dtype=int);ns=[149869,173651]
x=np.load(T/'transient_X/modal_coordinates.npy');times=[1+1/16384,1+4/16384];rows=[x[np.argmin(abs(x[:,0]-t))] for t in times]
lines=['/batch','resume,file,db','allsel,all','/post1','file,modes,rst','inres,nsol,strs','rsys,solu','esel,s,elem,,73331,112344','nsel,all','lcdef,erase','*cfopen,modal_nodes,csv']
for mode in range(1,39):
 lines += [f'set,1,{mode}',f'lcdef,{mode},1,{mode}']
 for n in ns:
  for k,comp in enumerate(['X','Y','Z','XY','YZ','XZ']):
   lines += [f'*get,PBS,node,{n},S,{comp}',f'*vwrite,{mode},{n},{k+1},PBS',"(F4.0,',',F9.0,',',F2.0,',',E24.16)"]
lines += ['*cfclos','file,seed,rst','set,1,1','reswrite,motion','file,modes,rst','*cfopen,combined_nodes,csv']
for i,row in enumerate(rows):
 lines += ['file,modes,rst','set,1,1','lcoper,zero']
 for j in range(1,39):lines += [f'lcfact,{j},{row[j]:.16e}']
 lines += ['lcoper,add,all']
 for n in ns:
  for k,comp in enumerate(['X','Y','Z','XY','YZ','XZ']):
   lines += [f'*get,PBS,node,{n},S,{comp}',f'*vwrite,{i+1},{n},{k+1},PBS',"(F4.0,',',F9.0,',',F2.0,',',E24.16)"]
 lines += ['file,motion,rst',f'rappnd,{i+2},{row[0]:.16e}']
lines += ['*cfclos','file,motion,rst','set,list','finish','/exit,nosave'];s='\n'.join(lines)+'\n';(O/'run.dat').write_text(s)
sha=json.loads((T/'stress_lcproof/manifest.json').read_text())['source_rst_sha256'];(O/'manifest.json').write_text(json.dumps({'no_solve':True,'nodes':ns,'seed_result_excluded_from_animation':True,'times_s':times,'q_source':'transient_X/modal_coordinates.npy','source_rst_sha256':sha,'run_sha256':hashlib.sha256(s.encode()).hexdigest(),'qualification':'Linear modal stress tensor superposition about the preload state; dynamic increments only, no static preload stresses added.'},indent=2))
win=lambda p:'\\\\Mac\\Home'+str(p).split('/Users/mdn',1)[1].replace('/','\\')
ps=r'''$ErrorActionPreference='Stop'
if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){throw 'Solver already active'}
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f ansys -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'Structural seat busy'}
$rt='C:\Temp\PBMotion_20261005_stress_lcproof_v4'
New-Item -ItemType Directory -Path $rt -ErrorAction Stop | Out-Null
$src='C:\Temp\PCBRV_20261005_X_local\file.rst'
if((Get-FileHash $src).Hash.ToLower() -ne 'SHA'){throw 'Source mode result mismatch'}
New-Item -ItemType HardLink -Path "$rt\modes.rst" -Target $src | Out-Null
New-Item -ItemType HardLink -Path "$rt\seed.rst" -Target 'C:\Temp\PBMotion_20261005_expand_X\file.rst' | Out-Null
Copy-Item 'DB' "$rt\file.db"
Copy-Item 'OUT\run.dat' $rt
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p ansys -j file -i run.dat -o run.out' -WorkingDirectory $rt -PassThru -Wait
Copy-Item "$rt\run.out","$rt\file.err","$rt\modal_nodes.csv","$rt\combined_nodes.csv" 'OUT'
$p.ExitCode | Out-File 'OUT\exit_code.txt'
'''.replace('SHA',sha).replace('DB',win(R/'modal_basis/file.db')).replace('OUT',win(O))
(T/'control/stress_lcproof_v4.ps1').write_text(ps)
print('Prepared',O)

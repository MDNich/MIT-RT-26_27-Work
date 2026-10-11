from pathlib import Path
import numpy as np,json,hashlib
T=Path(__file__).resolve().parents[1];O=T/'postproof';O.mkdir(exist_ok=True)
x=np.load(T/'pilot_X_32768/modal_coordinates.npy');indices=[6554,6556];lines=['/batch','resume,file,db','allsel,all','/post1','file,modes,rst','inres,nsol','lcdef,erase']
for j in range(1,39):lines.append(f'lcdef,{j},1,{j}')
for i,idx in enumerate(indices):
 row=x[idx];lines+=['file,modes,rst','lcoper,zero']
 for j in range(1,39):lines += [f'lcfact,{j},{row[j]:.16e}']
 lines+=['lcoper,add,all','file,motion,rst',f'rappnd,{i+1},{row[0]:.16e}']
 for node in [44,42154,42242,136765]:
  lines += [f'*get,U1,node,{node},u,x',f'*get,U2,node,{node},u,y',f'*get,U3,node,{node},u,z',f'/com,CHECK,{i+1},{node},%U1%,%U2%,%U3%']
lines+=['file,motion,rst','set,list','finish','/exit,nosave'];s='\n'.join(lines)+'\n';(O/'run.dat').write_text(s);(O/'manifest.json').write_text(json.dumps({'source':'pilot_X_32768','sample_indices':indices,'times_s':x[indices,0].tolist(),'sha256':hashlib.sha256(s.encode()).hexdigest(),'license':'preppost','no_solve':True},indent=2))
win=lambda p:'\\\\Mac\\Home\\'+str(p).split('/Users/mdn/',1)[1].replace('/','\\')
ps=r'''$ErrorActionPreference='Stop'
$lic=& 'C:\Program Files\ANSYS Inc\v261\licensingclient\winx64\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25
if(($lic -join ' ') -notmatch 'Total of 0 licenses? in use'){throw 'PrepPost seat busy'}
$rt='C:\Temp\PBMotion_20261005_postproof'
New-Item -ItemType Directory -Path $rt -ErrorAction Stop | Out-Null
Copy-Item 'C:\Temp\PBMotion_20261005_basis_smp\file.db' $rt
Copy-Item 'SRC\file.rst' "$rt\modes.rst"
Copy-Item 'OUT\run.dat' $rt
$p=Start-Process 'C:\Program Files\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe' -ArgumentList '-b nolist -smp -np 1 -p preppost -j file -i run.dat -o run.out' -WorkingDirectory $rt -PassThru -Wait
Copy-Item "$rt\run.out","$rt\file.err" 'OUT'
Get-ChildItem $rt -File | Select-Object Name,Length | ConvertTo-Csv -NoTypeInformation | Out-File 'OUT\inventory.csv'
'''.replace('SRC',win(T.parents[1]/'outputs/random_vibration_20261005_0950/modal_basis')).replace('OUT',win(O))
(T/'control/postproof.ps1').write_text(ps)

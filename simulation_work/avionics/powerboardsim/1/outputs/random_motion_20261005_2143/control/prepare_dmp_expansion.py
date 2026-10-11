from pathlib import Path
import json,subprocess,sys
T=Path(__file__).resolve().parents[1];name,source=sys.argv[1:3]
subprocess.run([sys.executable,str(T/'control/prepare_expansion.py')]+sys.argv[1:],check=True)
O=T/name;m=json.loads((O/'manifest.json').read_text());m['parallel_mode']='dmp';m['ranks']=12;(O/'manifest.json').write_text(json.dumps(m,indent=2))
p=T/'control'/('stage_'+name+'.ps1');s=p.read_text().replace("'^file\\.(db|mode|full|mlv|enf|rdsp)$'","'^file\\d*\\.(db|mode|full|mlv|enf|rdsp)$'")
start=s.index("Copy-Item 'C:\\Temp\\PBMotion_20261005_basis_aux_smp");end=s.index('\n',start)
s=s[:start]+"Get-ChildItem 'C:\\Temp\\PBMotion_20261005_basis' -File | Where-Object {$_.Name -match '^file\\d*\\.(emat|esav)$'} | Copy-Item -Destination '"+m['runtime']+"'"+s[end:]
p.write_text(s)

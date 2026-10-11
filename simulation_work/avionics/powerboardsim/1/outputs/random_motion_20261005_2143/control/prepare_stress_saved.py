from pathlib import Path
import json,hashlib,re,datetime
T=Path(__file__).resolve().parents[1];B=T/'basis_saved';name='stress_X_saved';O=T/name;O.mkdir(exist_ok=False)
s=(B/'solve.out').read_text();assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',s);assert 'NUMBER OF STATIC SHAPES =      3' in s
assert s.index('ALL CURRENT MAPDL DATA WRITTEN')>s.index('FINISH SOLUTION PROCESSING')
(B/'ACCEPTED.json').write_text(json.dumps({'finished':'2026-10-06T10:06:49-04:00','errors':0,'enforced_static_shapes':3,'source_mode_count':38,'ranks':12,'save_after_finish':True,'warnings':'7 inherited shape-testing, contact overlap/MPC and nonstructural material warnings; see file0.err','stress_expansion_validation':'pending'},indent=2))
old=T/'stress_X_dmp';run=(old/'run.dat').read_text().replace('time,1.05','time,1.0625').replace('save,file,db\nfinish','finish\nsave,file,db');pre=(old/'preflight.dat').read_text().replace('time,1.05','time,1.0625')
pre=pre.replace('/com,PREFLIGHT_TIMEHISTORY_INPUT_LOADED','''*cfopen,basis_frequencies,csv
*do,PBI,1,38
*get,PBF,mode,PBI,freq
*vwrite,PBI,PBF
(F4.0,',',E24.16)
*enddo
*cfclos
/com,PREFLIGHT_TIMEHISTORY_INPUT_LOADED''')
(O/'run.dat').write_text(run);(O/'preflight.dat').write_text(pre)
m=json.loads((old/'manifest.json').read_text());m.update(name=name,duration_s=1.0625,runtime=r'C:\Temp\PBMotion_20261005_'+name,run_sha256=hashlib.sha256(run.encode()).hexdigest(),preflight_sha256=hashlib.sha256(pre.encode()).hexdigest(),source='basis_saved');(O/'manifest.json').write_text(json.dumps(m,indent=2))
ps=(T/'control/stage_stress_X_dmp.ps1').read_text().replace('stress_X_dmp',name).replace("C:\\Temp\\PBMotion_20261005_basis'","C:\\Temp\\PBMotion_20261005_basis_saved'")
ps=ps.replace('lmstat -f preppost','lmstat -f ansys').replace("throw 'PrepPost seat busy'","throw 'Structural seat busy'").replace('-p preppost','-p ansys')
ps+="\nCopy-Item '"+m['runtime']+"\\basis_frequencies.csv' '"+('\\'*2+'Mac\\Home\\')+str(O).split('/Users/mdn/')[1].replace('/','\\')+"'\n"
(T/'control'/('stage_'+name+'.ps1')).write_text(ps)
print(O)

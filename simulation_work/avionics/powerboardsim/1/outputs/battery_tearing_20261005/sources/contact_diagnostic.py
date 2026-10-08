"""Separate read-only contact summary; never calls SOLVE or edits a result file."""
from pathlib import Path
import sys,json,hashlib,subprocess,re
S=Path(__file__).resolve().parent.parent
case,action=sys.argv[1:3];d=S/'runtime'/case;rt=r'C:\Temp\PBTear26_'+case

def win(p):return 'Z:'+str(p).removeprefix('/Users/mdn').replace('/','\\')
def ps(v):
 r=subprocess.run([sys.executable,str(S/'sources/vm_ps.py')],input="$ErrorActionPreference='Stop'\n"+v,text=True,capture_output=True,timeout=55)
 print(r.stdout)
 if r.returncode:raise RuntimeError(r.stderr)
 return r.stdout
if action=='prepare':
 deck='''/BATCH
RESUME,model,db
/POST1
FILE,tear,rst
/NOPR
SET,LAST
*GET,NSETS,ACTIVE,0,SET,NSET
*CFOPEN,contact_history,csv
*VWRITE
('set,loadstep,substep,time,max_pressure_MPa,max_friction_MPa,max_slide_mm,open_near,open_far,sliding,sticking')
*DO,KK,1,NSETS
 ALLSEL,ALL
 SET,,,,,,,KK
 *GET,LS,ACTIVE,0,SET,LSTP
 *GET,SB,ACTIVE,0,SET,SBST
 *IF,SB,EQ,999999,THEN
  *CYCLE
 *ENDIF
 *GET,TT,ACTIVE,0,SET,TIME
 ESEL,S,TYPE,,3
 ETABLE,ERAS
 ETABLE,CSTAT,NMISC,41
 ETABLE,CPRES,CONT,PRES
 ETABLE,CFRIC,CONT,SFRIC
 ETABLE,CSLID,CONT,SLIDE
 ESORT,ETAB,CPRES,0,0
 *GET,PMAX,SORT,0,MAX
 ESORT,ETAB,CFRIC,0,0
 *GET,FMAX,SORT,0,MAX
 ESORT,ETAB,CSLID,0,0
 *GET,SMAX,SORT,0,MAX
 ESEL,R,ETAB,CSTAT,0
 *GET,NOPEN,ELEM,0,COUNT
 ESEL,S,TYPE,,3
 ESEL,R,ETAB,CSTAT,1
 *GET,NNEAR,ELEM,0,COUNT
 ESEL,S,TYPE,,3
 ESEL,R,ETAB,CSTAT,2
 *GET,NSLIP,ELEM,0,COUNT
 ESEL,S,TYPE,,3
 ESEL,R,ETAB,CSTAT,3
 *GET,NSTIC,ELEM,0,COUNT
 *VWRITE,KK,LS,SB,TT,PMAX,FMAX,SMAX,NNEAR,NOPEN,NSLIP,NSTIC
 (3(F9.0,','),4(E19.11,','),3(F9.0,','),F9.0)
*ENDDO
*CFCLOS
FINISH
/EXIT,NOSAVE
'''
 assert '\nSOLVE' not in deck and 'ANTYPE' not in deck
 f=d/'contact_post.dat';assert not f.exists();f.write_text(deck)
 (d/'contact_post_sha256.json').write_text(json.dumps({'post.dat_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'qualification':'read-only result extraction, no model change; element status is highest integration-point status; slide includes accumulated tangential motion, not a weld-separation law'},indent=2))
elif action=='run':
 assert not (d/'CONTACT_POST_STARTED.txt').exists()
 lic=ps("& 'C:\\Program Files\\ANSYS Inc\\v261\\licensingclient\\winx64\\lmutil.exe' lmstat -f preppost -c 1055@MARCDNICHITBF25")
 assert re.search('Total of 0 licenses? in use',lic),'PrepPost busy'
 out=ps(f"if((Test-Path '{rt}\\tear.lock') -or (Test-Path '{rt}\\cdiag.lock')){{throw 'Runtime active'}}\nCopy-Item '{win(d)}\\contact_post.dat' '{rt}\\contact_post.dat'\n$p=Start-Process 'C:\\Program Files\\ANSYS Inc\\v261\\ansys\\bin\\winx64\\ANSYS261.exe' -ArgumentList '-b nolist -s noread -smp -np 1 -p preppost -j cdiag -i contact_post.dat -o contact_post.out' -WorkingDirectory '{rt}' -PassThru\n$p.Id")
 (d/'CONTACT_POST_STARTED.txt').write_text(out.strip())
elif action=='collect':
 ps(f"if(Test-Path '{rt}\\cdiag.lock'){{throw 'Postprocessing still active'}}\nCopy-Item '{rt}\\contact_post.out','{rt}\\cdiag.err','{rt}\\contact_history.csv' '{win(d)}'")
 text=(d/'contact_post.out').read_text(errors='replace');assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',text)
 (d/'CONTACT_POST_VERIFIED.txt').write_text(hashlib.sha256((d/'contact_post.out').read_bytes()).hexdigest())
 print('Contact extraction has zero native errors; interpret element statuses, not integration-point fractions.')
else:raise ValueError(action)

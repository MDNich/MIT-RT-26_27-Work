from pull_paths import *
import sys,subprocess,re,shutil,json
case=sys.argv[1];license_name=sys.argv[2] if len(sys.argv)>2 else 'preppost';D=S/'runtime'/case;rt='C:\\Temp\\PBpull_'+case
s=(D/'run.dat').read_text();s=s[s.index('/POST1'):]
s=s.replace('*GET,RR,NODE','RR=0\n*GET,RR,NODE').replace('*GET,W1F,NODE','W1F=0\n*GET,W1F,NODE').replace('*GET,W2F,NODE','W2F=0\n*GET,W2F,NODE')
cfg=json.loads((D/'config.json').read_text())
if 'mu' in cfg:
 e=['/POST1','SET,LAST','*GET,NSET,ACTIVE,0,SET,NSET','*CFOPEN,contact_detail,csv','*VWRITE',"('set,time,max_pen_mm,max_plastic_slip_mm,max_elastic_slip_mm')",'*DO,II,1,NSET','SET,,,,,,,II','*GET,TT,ACTIVE,0,SET,TIME','CMSEL,S,CLAMP_CONTACT','ETABLE,CPP,CONT,PENE','ESORT,ETAB,CPP,0,0','*GET,PPMAX,SORT,0,MAX','PSMAX=0','ESMAX=0']
 for prefix,first,out in [('P',164,'PSMAX'),('E',136,'ESMAX')]:
  for j in range(4):
   e += [f'ETABLE,{prefix}{j},NMISC,{first+j}',f'ESORT,ETAB,{prefix}{j},0,0','*GET,SMM,SORT,0,MAX',f'{out}=MAX({out},SMM)']
 e += ['*VWRITE,II,TT,PPMAX,PSMAX,ESMAX',"(F8.0,4(',',E19.11))",'ALLSEL,ALL','*ENDDO','*CFCLOS']
 s=s.replace('FINISH\n/EXIT,NOSAVE','\n'.join(e)+'\nFINISH\n/EXIT,NOSAVE')
if 'mu' in cfg:
 mesh=json.loads((D/'mesh.json').read_text())
 refnodes=cfg.get('target_pilots',mesh['clamp'])+[mesh['pilot']]
 e=['/POST1','SET,LAST','*GET,NSET,ACTIVE,0,SET,NSET','*CFOPEN,moment_balance,csv','*VWRITE',"('set,time,mx_Nmm,my_Nmm,mz_Nmm')",'*DO,II,1,NSET','SET,,,,,,,II','RSYS,0','*GET,TT,ACTIVE,0,SET,TIME','XM=0','YM=0','ZM=0']
 for nd in refnodes:
  for ax in 'XYZ':
   e += [f'*GET,{ax}P,NODE,{nd},LOC,{ax}',f'*GET,{ax}U,NODE,{nd},U,{ax}',f'{ax}P={ax}P+{ax}U',f'{ax}F=0',f'*GET,{ax}F,NODE,{nd},RF,F{ax}',f'{ax}R=0',f'*GET,{ax}R,NODE,{nd},RF,M{ax}']
  e += ['XM=XM+XR+YP*ZF-ZP*YF','YM=YM+YR+ZP*XF-XP*ZF','ZM=ZM+ZR+XP*YF-YP*XF']
  if nd in cfg.get('bottom_pilots',[]):
   e += ['*IF,TT,LE,1,THEN','XM=XM+YP*750*TT','YM=YM-XP*750*TT','*ENDIF']
 e += ['*VWRITE,II,TT,XM,YM,ZM',"(F8.0,4(',',E19.11))",'*ENDDO','*CFCLOS']
 s=s.replace('FINISH\n/EXIT,NOSAVE','\n'.join(e)+'\nFINISH\n/EXIT,NOSAVE')
s='RESUME,solved,db\n/POST1\nFILE,pull,rst\n/NOPR\n'+s
(D/'post_corrected.dat').write_text(s)
backup=D/'post_original';backup.mkdir(exist_ok=True)
for f in D.glob('*.csv'):
 if not (backup/f.name).exists():shutil.copy2(f,backup/f.name)
ps=f"""if(Get-Process ANSYS,ANSYS261 -ErrorAction SilentlyContinue){{throw 'Solver exists'}}
Copy-Item '{win(D)}\\post_corrected.dat' '{rt}'
$p=Start-Process 'C:\\Program Files\\ANSYS Inc\\v261\\ansys\\bin\\winx64\\ANSYS261.exe' -ArgumentList '-b nolist -s noread -smp -np 1 -p {license_name} -j post -i post_corrected.dat -o post_corrected.out' -WorkingDirectory '{rt}' -PassThru -Wait
$p.ExitCode
"""
z=subprocess.run(['python3','/tmp/powerboard_vm.py'],input=ps,text=True,capture_output=True);print(z.stdout,z.stderr);z.check_returncode()
ps=f"Get-ChildItem '{rt}' -File | Where-Object {{ $_.Extension -eq '.csv' -or $_.Name -in 'post_corrected.out','post.err' }} | Copy-Item -Destination '{win(D)}'"
z=subprocess.run(['python3','/tmp/powerboard_vm.py'],input=ps,text=True,capture_output=True);print(z.stdout,z.stderr);z.check_returncode()
assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',(D/'post_corrected.out').read_text(errors='replace'))
print('POST CORRECTED',case)

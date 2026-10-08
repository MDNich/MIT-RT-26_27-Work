from rv_paths import *
import re,json,hashlib,sys,csv
axis=sys.argv[1];assert axis in ['X','Y','Z']
C=R/axis
assert (C/'SOLVED.txt').exists()
s=(C/'solve.out').read_text(errors='replace');deck=(C/'ds.dat').read_text()
assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',s)
assert 'ALL MODES FROM THE MODAL ANALYSIS ARE SELECTED FOR COMBINATION.' in s
assert re.search(r'DAMPING RATIO\s*=\s*0.0200',s)
assert len(re.findall('FIXED RELATIVE MOTION=',s))>=6
assert re.search(r'(?im)^PSDUNIT,1,ACEL$',deck)
assert 'psdres,disp,rel' in deck.lower()
assert 'psdres,acel,abs' in deck.lower()
assert re.search(r'(?im)^d,all,u'+axis.lower()+',1',deck)
for match in re.finditer(r'PBANALYSIS\s+FROM\s+ACTI\s+ITEM=ANTY\s+VALUE=\s*([0-9.]+)',s):assert float(match[1])==8
blocks=re.split(r'\*\*\* (DISPLACEMENT|VELOCITY|ACCELERATION)-TYPE QUANTITY \*\*\*',s)
diag={}
for i in range(1,len(blocks),2):
 vals=[]
 for l in blocks[i+1].splitlines():
  t=l.split()
  if len(t)==4 and t[0].isdigit() and t[1].isdigit() and t[0]==t[1]:
   vals.append({'mode':int(t[0]),'covariance':float(t[2]),'ratio':float(t[3])})
 if vals:diag[blocks[i]]=sorted(vals,key=lambda x:x['covariance'],reverse=True)[:5]
manifest={'axis':axis,'analysis_id':dict(X=4259,Y=4264,Z=4269)[axis],'errors':0,'warnings':int(re.search(r'NUMBER OF WARNING\s+MESSAGES ENCOUNTERED=\s*(\d+)',s)[1]),'damping':0.02,'modes':38,'mounted_nodes':781,'gravity_m_s2':9.80665,'six_locked_pretensions':True,'modal_diagonal_terms':diag,'sha256':{n:hashlib.sha256((C/n).read_bytes()).hexdigest() for n in ['ds.dat','solve.out','psd_input.dat']}}
(C/'solver_audit.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))

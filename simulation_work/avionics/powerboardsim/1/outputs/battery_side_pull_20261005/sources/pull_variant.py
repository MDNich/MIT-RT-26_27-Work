from pull_paths import *
import sys,json,hashlib
base,case,kind=sys.argv[1:4];B=S/'runtime'/base;D=S/'runtime'/case;D.mkdir(exist_ok=True)
for f in ['model.inp','preflight.dat','run.dat','mesh.json','config.json']:
 t=(B/f).read_text()
 if f.endswith(('.inp','.dat')):
  if kind=='lagrange':t=t.replace('KEYOPT,2,2,0','KEYOPT,2,2,1')
  if kind=='nostress':t=t.replace('KEYOPT,2,2,0','KEYOPT,2,2,0\nKEYOPT,2,5,1')
 if f=='config.json':
  c=json.loads(t);c['case']=case;c['rigid_coupling_variant']=kind;t=json.dumps(c,indent=2)
 (D/f).write_text(t)
(D/'input_sha256.json').write_text(json.dumps({f:hashlib.sha256((D/f).read_bytes()).hexdigest() for f in ['model.inp','preflight.dat','run.dat','mesh.json','config.json']},indent=2))

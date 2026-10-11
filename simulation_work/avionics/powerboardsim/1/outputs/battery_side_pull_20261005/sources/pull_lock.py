from pull_paths import *
import sys,json,hashlib
base,case=sys.argv[1:3];B=S/'runtime'/base;D=S/'runtime'/case;D.mkdir(exist_ok=True)
assert not (D/'SOLVE_STARTED.txt').exists()
cfg=json.loads((B/'config.json').read_text());pilot=json.loads((B/'mesh.json').read_text())['pilot']
for f in ['model.inp','preflight.dat','run.dat','mesh.json']:
 s=(B/f).read_text()
 if f=='run.dat':
  # Force-to-displacement transfer at the converged preload, no lateral movement.
  anchor=f'DDELE,{pilot},UY'
  assert s.count(anchor)==1
  s=s.replace(anchor,'KBC,1\nTIME,2\nNSUBST,1,100,1\nSOLVE\nKBC,0\n'+anchor)
  s=s.replace('TIME,2\nNSUBST,100,4000,20','TIME,3\nNSUBST,100,4000,20')
  s=s.replace('*GET,RR,NODE','RR=0\n*GET,RR,NODE').replace('*GET,W1F,NODE','W1F=0\n*GET,W1F,NODE').replace('*GET,W2F,NODE','W2F=0\n*GET,W2F,NODE')
  s=s.replace('/POST1','/POST1\n/NOPR',1)
 (D/f).write_text(s)
cfg.update(case=case,pull_start_time=2,end_time=3,load_protocol='Step1 750 N per washer; step2 KBC=1 transfer to locked UZ at UX=0 and held battery; step3 KBC=0 pull with other battery DOFs free')
(D/'config.json').write_text(json.dumps(cfg,indent=2))
(D/'input_sha256.json').write_text(json.dumps({f:hashlib.sha256((D/f).read_bytes()).hexdigest() for f in ['model.inp','preflight.dat','run.dat','mesh.json','config.json']},indent=2))
print(case)

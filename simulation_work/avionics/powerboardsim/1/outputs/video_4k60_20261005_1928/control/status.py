from paths import *
from finalize import gallery
import json,datetime
jobs=json.loads((V/'manifest.json').read_text());done=[];active=[]
for j in jobs:
 w=V/j['name']
 if (w/'ENCODED.json').exists():done.append(j['name'])
 elif (w/'COMPLETE.txt').exists():active.append(j['name']+': encoding')
 elif (w/'STARTED.txt').exists() and j['kind']=='rms':active.append(j['name']+': '+((w/'progress.txt').read_text() if (w/'progress.txt').exists() else 'starting'))
 elif j['kind']=='modal' and (w/'native_frames').exists():active.append(j['name']+': '+str(len(list((w/'native_frames').glob('*.png'))))+'/180 native frames')
print(datetime.datetime.now().isoformat(timespec='seconds'),'Ready',len(done),'/20; RMS',sum(n.startswith('random') for n in done),'/17')
print('\n'.join(active))
if (OLD/'request_error.txt').exists():print('ERROR:',(OLD/'request_error.txt').read_text())
gallery()

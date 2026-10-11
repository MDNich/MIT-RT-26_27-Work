from paths import *
from encode import encode
import json,time,subprocess,sys,concurrent.futures,traceback,signal
jobs=json.loads((V/'manifest.json').read_text());control=Path(__file__).parent
priority=['random_fig06_baseX_responseX','random_fig07_baseX_responseY','random_fig08_baseX_responseZ']
jobs.sort(key=lambda j: (priority.index(j['name']) if j['name'] in priority else 3 if j['kind']=='rms' else 4))
paused=False
def pause(signum,frame):
 global paused
 paused=True
 (V/'PAUSE_REQUESTED.txt').write_text(time.strftime('%Y-%m-%d %H:%M:%S'))
 print('Pause requested; no further jobs will be submitted.',flush=True)
signal.signal(signal.SIGINT,pause);signal.signal(signal.SIGTERM,pause)
def status(s):
 line=time.strftime('%Y-%m-%d %H:%M:%S')+' '+s
 print(line,flush=True)
 with (V/'batch_status.txt').open('a') as f:f.write(line+'\n')
if (V/'PAUSE_REQUESTED.txt').exists():raise RuntimeError('Remove PAUSE_REQUESTED.txt only after explicit user resume')
try:
 with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
  futures=[]
  for j in jobs:
   if paused:break
   w=V/j['name'];done=w/'COMPLETE.txt'
   if not done.exists():
    assert not (OLD/'request.py').exists()
    if '--running-job='+j['name'] in sys.argv:
     assert (OLD/'active.py').read_text()==(w/'export.py').read_text()
     assert not (OLD/'request_done.txt').exists() and not (OLD/'request_error.txt').exists()
    else:
     subprocess.run([sys.executable,str(control/'request.py')],input=(w/'export.py').read_text(),text=True,check=True)
    status('RENDERING '+j['name']);t0=time.monotonic()
    while not done.exists():
     if paused:break
     if (OLD/'request_error.txt').exists():raise RuntimeError((OLD/'request_error.txt').read_text())
     if time.monotonic()-t0>1200:raise TimeoutError(j['name'])
     time.sleep(3)
    if paused:break
   status('RENDERED '+j['name'])
   while not (OLD/'request_done.txt').exists() and not (w/'ENCODED.json').exists():
    if paused:break
    time.sleep(0.5)
   if paused:break
   futures.append(pool.submit(encode,j))
   for f in futures:
    if f.done():f.result()
  for f in futures:f.result()
 if paused:status('PAUSED; completed files and partial frames preserved')
 else:
  assert len(list(V.glob('*/ENCODED.json')))==20
  (V/'ALL_COMPLETE.txt').write_text(time.strftime('%Y-%m-%d %H:%M:%S'))
  status('COMPLETE: 20 videos rendered and encoded')
except Exception:
 status('FAILED '+traceback.format_exc());raise

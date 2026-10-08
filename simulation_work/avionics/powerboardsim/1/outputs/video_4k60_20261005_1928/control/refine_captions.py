from paths import *
from encode import encode
from finalize import gallery
import json,time
jobs=json.loads((V/'manifest.json').read_text())
while True:
 ready=0
 for j in jobs:
  p=V/j['name']/'ENCODED.json'
  if not p.exists():continue
  info=json.loads(p.read_text())
  if info.get('processing_revision')==2:ready+=1;continue
  if time.time()-p.stat().st_mtime<10:continue
  encode(j,force=True);ready+=1
 gallery()
 if ready==len(jobs):
  (V/'CAPTIONS_COMPLETE.txt').write_text(time.strftime('%Y-%m-%d %H:%M:%S'));break
 if (V/'PAUSE_REQUESTED.txt').exists():break
 time.sleep(10)

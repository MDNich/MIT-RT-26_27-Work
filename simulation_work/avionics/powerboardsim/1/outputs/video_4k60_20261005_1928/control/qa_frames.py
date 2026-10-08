from paths import *
import subprocess,json,io
from PIL import Image
import numpy as np
jobs=json.loads((V/'manifest.json').read_text())
for j in jobs:
 w=V/j['name'];marker=w/'ENCODED.json';out=w/'visual_frame_checks.json'
 if not marker.exists() or json.loads(marker.read_text()).get('processing_revision')!=2:continue
 if out.exists() and out.stat().st_mtime>marker.stat().st_mtime:continue
 clip=D/(j['name']+'.mp4');rows=[];geometry=[]
 src=sorted((w/'native_frames').glob('*.png')) if j['kind']=='modal' else sorted(w.glob('frame_*.png'))
 for n in [0,60,120]:
  data=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-ss',str(n/60),'-i',str(clip),'-frames:v','1','-f','image2pipe','-vcodec','png','-'])
  frame=np.asarray(Image.open(io.BytesIO(data)).convert('RGB'));raw=np.asarray(Image.open(src[n]).convert('RGB'))
  a=frame[450:1900,950:3350].astype(np.int16);b=raw[450:1900,950:3350].astype(np.int16)
  mae=float(np.mean(np.abs(a-b)));assert mae<4.0,(j['name'],n,mae)
  footer=frame[2080:2145,30:2670];bright=int(np.sum(np.min(footer,axis=2)>170));assert bright>1000,(j['name'],'caption missing')
  rows.append({'frame':n,'mean_abs_RGB_difference_in_geometry_vs_native_PNG':mae,'bright_caption_pixels':bright});geometry.append(a)
 motion=float(np.mean(np.abs(geometry[0]-geometry[-1])));assert motion>0.1,(j['name'],'no detected motion')
 out.write_text(json.dumps({'samples':rows,'mean_abs_RGB_change_frame0_to120':motion},indent=2));print('QA',j['name'],'motion',round(motion,2),flush=True)

from pathlib import Path
from PIL import Image
import sys,zipfile,hashlib,json,shutil
O=Path(r'C:\Temp\PBMotionVideos\modal_fig03_bolted_mode20');D=Path(sys.argv[1]);D.mkdir(exist_ok=True,parents=True)
assert (O/'COMPLETE.txt').exists()
files=sorted((O/'frames').glob('*.png'));assert len(files)==180
records=[]
with zipfile.ZipFile(O/'frames_png.zip','w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
 for i,p in enumerate(files):
  assert p.name=='AnimationFrame%06d.png'%i
  with Image.open(p) as im:assert im.size==(3840,2160);im.verify()
  data=p.read_bytes();z.writestr(p.name,data);records.append({'name':p.name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
assert len({r['sha256'] for r in records})>=90
(O/'FRAMES_VALIDATED.json').write_text(json.dumps({'count':180,'width':3840,'height':2160,'unique_pngs':len({r['sha256'] for r in records}),'source':'Mechanical native Python Result contour and warp fields','frames':records},indent=2))
for name in ['frames_png.zip','FRAMES_VALIDATED.json','field_audit.txt','camera_audit.txt','legend_verified.png']:
 shutil.copyfile(O/name,D/name)
(D/'COLLECTED.txt').write_text('180 native 4K phase frames verified.\n')
print('COLLECTED',D)

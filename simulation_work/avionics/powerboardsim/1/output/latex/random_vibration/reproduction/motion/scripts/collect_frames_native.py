from pathlib import Path
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import sys,io,zipfile,json,hashlib,shutil,datetime
O=Path(sys.argv[1]);D=Path(sys.argv[2])
files=sorted((O/'frames').glob('*.png'));assert len(files)==480,(len(files),O)
assert [p.stem for p in files]==['AnimationFrame%06d'%i for i in range(480)]
def convert(p):
 with Image.open(p) as im:
  assert im.size==(3840,2160),(p,im.size);im.verify()
 data=p.read_bytes()
 return p.name,data,hashlib.sha256(data).hexdigest()
ziptmp=O/'frames_png.zip.tmp';records=[]
with zipfile.ZipFile(ziptmp,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
 with ThreadPoolExecutor(max_workers=2) as pool:
  for name,data,sha in pool.map(convert,files):
   z.writestr(name,data);records.append({'name':name,'sha256':sha,'bytes':len(data)})
zipfinal=O/'frames_png.zip';ziptmp.replace(zipfinal)
a={'count':480,'width':3840,'height':2160,'unique_pngs':len({r['sha256'] for r in records}),'source':'Native Mechanical PNG animation frames, unchanged','frames':records};assert a['unique_pngs']==480
(O/'FRAMES_VALIDATED.json').write_text(json.dumps(a,indent=2))
D.mkdir(exist_ok=True,parents=True)
for name in ['frames_png.zip','legend_verified.png',('legend_bound_Pa.txt' if (O/'legend_bound_Pa.txt').exists() else 'legend_bound_m.txt'),'FRAMES_VALIDATED.json'] + [n for n in ['frame_audit.csv','field_audit.txt','camera_audit.txt','REPAIR_AUDIT.txt','frame_audit_before_repair.csv'] if (O/n).exists()]:
 src=O/name;dest=D/(name+'.copying');shutil.copyfile(src,dest);dest.replace(D/name)
(D/'COMPLETE.txt').write_text('All 480 native PNG frames independently verified; optional native video encoding is separate.\n')
(D/'COLLECTED.txt').write_text(datetime.datetime.now().isoformat());print('COLLECTED',D,flush=True)

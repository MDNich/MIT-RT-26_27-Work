from pathlib import Path
import sys,json,zipfile,hashlib
from PIL import Image
T=Path(__file__).resolve().parents[1];O=T/'videos'/sys.argv[1];assert(O/'COLLECTED.txt').exists();a=json.loads((O/'FRAMES_VALIDATED.json').read_text());out=O/'frames';out.mkdir(exist_ok=True)
with zipfile.ZipFile(O/'frames_png.zip') as z:
 assert z.namelist()==['AnimationFrame%06d.png'%i for i in range(480)]
 for r in a['frames']:
  b=z.read(r['name']);assert hashlib.sha256(b).hexdigest()==r['sha256'];p=out/r['name'];p.write_bytes(b)
  with Image.open(p) as im:assert im.size==(3840,2160);im.verify()
m=json.loads((O/'manifest.json').read_text());m['contour_bound']=float((O/('legend_bound_Pa.txt' if (O/'legend_bound_Pa.txt').exists() else 'legend_bound_m.txt')).read_text());(O/'manifest.json').write_text(json.dumps(m,indent=2))
print('Verified',out,flush=True)

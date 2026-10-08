from pathlib import Path
import json,subprocess,hashlib,csv,re
T=Path(__file__).resolve().parents[1];P=T.parents[1];old=P/'output/videos/power_board_4k60';new=P/'output/videos/power_board_random_motion_4k60';FFP='/opt/homebrew/bin/ffprobe';rows=[]
for root in [old,new]:
 for p in sorted(root.glob('*.mp4')):
  if '.encoding.' in p.name:continue
  kind='seeded random motion' if root==new else ('normalized modal motion' if p.stem.startswith('modal') else 'camera motion over fixed RMS')
  info=json.loads(subprocess.check_output([FFP,'-v','error','-show_streams','-show_format','-of','json',str(p)]));v=info['streams'][0]
  expected=480 if kind=='seeded random motion' else (540 if kind=='normalized modal motion' else 480)
  assert v['width']==3840 and v['height']==2160 and v['r_frame_rate']=='60/1'
  assert int(v['nb_frames'])==expected,(p,v['nb_frames'],expected)
  rows.append({'file':str(p.relative_to(P/'output/videos')),'kind':kind,'width':3840,'height':2160,'fps':60,'frames':int(v['nb_frames']),'duration_s':float(v['duration']),'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()})
assert len(rows)==22,len(rows)
assert sum(r['kind']=='seeded random motion' for r in rows)==7
assert sum(r['kind']=='normalized modal motion' for r in rows)==3
assert sum(r['kind']=='camera motion over fixed RMS' for r in rows)==12
for root in [old,new]:
 for href in re.findall(r'(?:href|src|poster)="([^"]+)"',(root/'index.html').read_text()):
  if not href.startswith(('http','#')):assert (root/href).exists(),href
(P/'output/videos/DELIVERY_MANIFEST.json').write_text(json.dumps({'created':'2026-10-06','video_count':22,'actual_random_motion':7,'modal_motion':3,'legacy_RMS_camera_views':12,'videos':rows},indent=2))
with (P/'output/videos/DELIVERY_MANIFEST.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
new.joinpath('README.txt').write_text('''Seven actual random-vibration motion videos, native Mechanical 3840x2160 at 60 fps.
Open index.html. The camera is fixed; the assembly deforms according to three
separate accepted seeded time histories. Contours are instantaneous, not RMS.
Physical displacement is magnified 50 times. Playback is slowed 273.0667 times.
The stress video shows the dynamic unaveraged tensor's von Mises value; static
clamp stress is excluded. Six bolts have 750 N preload each; damping is 2%.
Large native result files, field audits and source PNGs remain in the project.
See the random-vibration report and its reproduction/motion/ supplement.
''')
print('DELIVERY VALIDATED',len(rows),'videos',sum(r['bytes'] for r in rows),'bytes')

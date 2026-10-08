from pathlib import Path
import json,html,hashlib,csv,shutil
T=Path(__file__).resolve().parents[1];P=T.parents[1];D=P/'output/videos/power_board_4k60';V=P/'outputs/video_4k60_20261005_1928';B=T/'gallery_backups';B.mkdir(exist_ok=True)
for n in ['index.html','README.txt','manifest.json','index.csv']:
 p=D/n
 if p.exists() and not(B/n).exists():shutil.copy2(p,B/n)
jobs=json.loads((V/'manifest.json').read_text());available=[];cards=[]
for j in jobs:
 p=D/(j['name']+'.mp4')
 if not p.exists():continue
 assert (V/j['name']/'ENCODED.json').exists()
 desc=('Normalized mode-shape motion; arbitrary amplitude and slowed playback.' if j['kind']=='modal' else 'Camera motion only. The RMS contour is fixed; this is not a vibration time history.')
 item={'name':j['name'],'title':j['title'],'kind':j['kind'],'description':desc,'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()};available.append(item)
 cards.append('<article><h2>'+html.escape(j['title'])+'</h2><p>'+desc+'</p><video controls preload="none" poster="'+j['name']+'.jpg" src="'+p.name+'"></video><a href="'+p.name+'">Open MP4</a></article>')
D.joinpath('index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Power board: modal motion and RMS camera views</title><style>body{font:17px system-ui;background:#14171c;color:#e8edf5;margin:32px auto;max-width:1150px;padding:0 24px}a{color:#82bfff}h1{font-size:32px}h2{font-size:21px}article{border-top:1px solid #424852;padding:24px 0}video{display:block;width:100%;margin:14px 0}p{line-height:1.6}</style><h1>Modal motion and RMS camera views</h1><p>Native Mechanical graphics, 3840 × 2160 at 60 fps. '''+str(len(available))+''' completed videos in this collection.</p><p><a href="../power_board_random_motion_4k60/index.html">Open the actual random-vibration motion videos →</a></p><p>The random-vibration clips below move the camera over a fixed statistical RMS field. The separate motion collection shows signed, time-dependent deformation from new transient calculations.</p>'''+''.join(cards))
D.joinpath('README.txt').write_text('''Power board native Mechanical videos: 4K / 60 fps.

This directory contains accepted modal motion clips and twelve older camera
views of fixed RMS fields. The camera clips do not show vibration in time.
Actual random-vibration motion is in ../power_board_random_motion_4k60/.
The default modal source is preserved and has not been re-solved with bolts.
See index.html and manifest.json for the files currently available.
''')
D.joinpath('manifest.json').write_text(json.dumps(available,indent=2))
with D.joinpath('index.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(available[0]));w.writeheader();w.writerows(available)
print('Published inventory:',len(available))

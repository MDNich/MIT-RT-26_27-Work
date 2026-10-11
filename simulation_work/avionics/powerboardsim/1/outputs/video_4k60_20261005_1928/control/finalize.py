from paths import *
import json, re, html, shutil, hashlib, subprocess, zipfile, sys
jobs=json.loads((V/'manifest.json').read_text())
def gallery():
 p=D/'index.html';s=p.read_text();cards=[]
 for j in jobs:
  n=j['name'];ready=(D/(n+'.mp4')).exists();fig=int(re.search(r'fig(\d+)',n)[1]);kind='Modal' if j['kind']=='modal' else 'Random vibration'
  card='<article data-kind="%s"><p class="tag">%s · Figure %d</p><h2>%s</h2>'%(j['kind'],kind,fig,html.escape(j['title']))
  card+=('<video controls loop playsinline preload="none" poster="%s.jpg" src="%s.mp4"></video>'%(n,n)) if ready else '<div class="pending">Export queued / rendering</div>'
  card+='<p>'+('Normalized mode shape · 9 seconds' if j['kind']=='modal' else 'Camera movement over a fixed RMS field · 8 seconds')+'</p>'
  card+=('<a href="%s.mp4" download>Download MP4</a>'%n) if ready else '<span>MP4 will appear here when ready.</span>'
  card+='<span class="meta">Result %s · 3840 × 2160 · 60 fps</span></article>'%j['result'];cards.append(card)
 p.write_text(re.sub(r'(<main class="grid">).*?(</main>)',lambda m:m[1]+''.join(cards)+m[2],s,flags=re.S))
def finalize():
 validation=[];hashes=[]
 for j in jobs:
  w=V/j['name'];f=D/(j['name']+'.mp4');assert f.exists() and (w/'ENCODED.json').exists(),j['name']
  assert json.loads((w/'ENCODED.json').read_text()).get('processing_revision')==2
  assert (w/'visual_frame_checks.json').stat().st_mtime>(w/'ENCODED.json').stat().st_mtime
  data=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-show_streams','-show_format','-of','json',str(f)]));st=data['streams'][0]
  assert (st['width'],st['height'],st['r_frame_rate'],int(st['nb_frames']))==(3840,2160,'60/1',540 if j['kind']=='modal' else 480)
  sha=hashlib.file_digest(f.open('rb'),'sha256').hexdigest();hashes.append(sha+'  '+f.name)
  validation.append({'file':f.name,'sha256':sha,'width':st['width'],'height':st['height'],'fps':st['r_frame_rate'],'frames':int(st['nb_frames']),'duration_s':float(st['duration']),'native_audit':(w/'audit.txt').read_text(),'full_decode_check':'passed before delivery (encode.py)','sample_frame_checks':json.loads((w/'visual_frame_checks.json').read_text())})
  rp=D/'reproduction'/j['name'];rp.mkdir(parents=True,exist_ok=True)
  for name in ['export.py','audit.txt','STARTED.txt','COMPLETE.txt','ENCODED.json','encode_command.json','encode.log','gpu.txt','caption.txt','visual_frame_checks.json']:
   if (w/name).exists():shutil.copy2(w/name,rp/name)
 cp=D/'reproduction/control';cp.mkdir(parents=True,exist_ok=True)
 for name in ['paths.py','encode.py','batch.py','request.py','finalize.py','qa_frames.py']:
  shutil.copy2(Path(__file__).parent/name,cp/name)
 (D/'SHA256SUMS.txt').write_text('\n'.join(hashes)+'\n');(D/'validation.json').write_text(json.dumps(validation,indent=2));gallery()
 z=D.with_suffix('.zip')
 with zipfile.ZipFile(z,'w',compression=zipfile.ZIP_STORED) as out:
  for f in sorted(D.rglob('*')):
   if f.is_file():out.write(f,f.relative_to(D.parent))
 print('Packaged',len(validation),'videos:',z)
if __name__=='__main__':
 gallery()
 if '--final' in sys.argv:finalize()

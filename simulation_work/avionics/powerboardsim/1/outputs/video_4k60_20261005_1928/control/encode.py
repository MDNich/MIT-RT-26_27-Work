from paths import *
import json,subprocess,os,shutil
FF='/opt/homebrew/bin/ffmpeg'; FP='/opt/homebrew/bin/ffprobe'
def encode(j,force=False):
 w=V/j['name'];dest=D/(j['name']+'.mp4')
 if (w/'ENCODED.json').exists() and not force:return
 assert (w/'COMPLETE.txt').exists()
 seq=w/'sequence';seq.mkdir(exist_ok=True)
 if j['kind']=='modal':
  src=sorted((w/'native_frames').glob('*.png'));assert len(src)==180,len(src)
  order=list(range(180))*3
  cap=j['title']+'  |  Normalized mode shape; magnified, slowed playback (3 s/cycle)'
 else:
  src=sorted(w.glob('frame_*.png'));assert len(src)==121,len(src)
  order=(list(range(121))+list(range(119,0,-1)))*2
  cap=j['title']+'  |  Camera motion only; RMS field fixed  |  750 N/bolt; damping 2%'
  if j['result']==4289:cap+='  |  Gaussian probability label does not apply'
 for i,n in enumerate(order):
  f=seq/('%04d.png'%i)
  if not f.exists():os.link(src[n],f)
 (w/'caption.txt').write_text(cap)
 args=[FF,'-hide_banner','-y','-framerate','60','-i',str(seq/'%04d.png')]
 if j['kind']=='modal':
  args+=['-loop','1','-i',str(w/'legend_source.png')]
  lw=1200 if j['name']=='modal_fig03_bolted_mode20' else 850
  filt='[1:v]crop=%d:1250:0:0[legend];[0:v][legend]overlay=0:0:shortest=1[base];[base]'%lw
 else:filt='[0:v]'
 fs='32' if j['result']==4289 else '36'
 filt+="drawbox=x=0:y=ih-100:w=2700:h=100:color=black@0.88:t=fill,drawtext=fontfile=/System/Library/Fonts/Supplemental/Arial.ttf:textfile="+str(w/'caption.txt')+":expansion=none:fontcolor=white:fontsize="+fs+":x=48:y=h-68[out]"
 temp=dest.with_suffix('.encoding.mp4')
 args+=['-filter_complex',filt,'-map','[out]','-an','-frames:v',str(len(order)),'-c:v','h264_videotoolbox','-allow_sw','0','-profile:v','high','-level:v','5.2','-b:v','80M','-maxrate','120M','-bufsize','240M','-pix_fmt','yuv420p','-r','60','-g','120','-tag:v','avc1','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-movflags','+faststart','-metadata','title='+j['title'],'-metadata','comment=Mechanical 2026 R1 native 4K frames; 60 fps. '+('Normalized mode animation, not physical amplitude/time.' if j['kind']=='modal' else 'Camera motion over fixed RMS contours, not a random time history.'),str(temp)]
 (w/'encode_command.json').write_text(json.dumps(args,indent=2))
 with (w/'encode.log').open('w') as f:subprocess.run(args,stdout=f,stderr=f,check=True)
 info=json.loads(subprocess.check_output([FP,'-v','error','-show_streams','-show_format','-of','json',str(temp)]));s=info['streams'][0]
 assert (s['width'],s['height'],s['r_frame_rate'],int(s['nb_frames']))==(3840,2160,'60/1',len(order))
 subprocess.run([FF,'-v','error','-i',str(temp),'-f','null','-'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
 assert not any(t in (w/'encode.log').read_text() for t in ['Stray %', 'Error', 'Failed']), 'Encoder warnings require review'
 temp.replace(dest);info['format']['filename']=str(dest);info['processing_revision']=2
 (w/'ENCODED.json').write_text(json.dumps(info,indent=2))
 for f in (w/'native_frames').glob('*.bmp'):f.unlink()
 shutil.rmtree(seq)
 subprocess.run([FF,'-v','error','-y','-ss','1','-i',str(dest),'-frames:v','1','-vf','scale=1280:-1',str(D/(j['name']+'.jpg'))],check=True)
 print('ENCODED',j['name'],flush=True)
if __name__=='__main__':
 import sys
 for j in json.loads((V/'manifest.json').read_text()):
  if not sys.argv[1:] or '--force' in sys.argv or j['name'] in sys.argv[1:]:
   if (V/j['name']/'COMPLETE.txt').exists():encode(j,force='--force' in sys.argv)

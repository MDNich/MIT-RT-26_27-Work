from pathlib import Path
import sys,json,subprocess,shutil
from PIL import Image
T=Path(__file__).resolve().parents[1];P=T.parents[1];D=P/'output/videos/power_board_random_motion_4k60';D.mkdir(exist_ok=True,parents=True)
FF='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe'
def encode(name):
 O=T/'videos'/name;m=json.loads((O/'manifest.json').read_text());assert(O/'COMPLETE.txt').exists();legend=O/'legend_relabeled.png';legend=legend if legend.exists() else O/'legend_verified.png';assert legend.exists();frames=sorted((O/'frames').glob('*.png'));assert len(frames)==480
 for p in [frames[0],frames[239],frames[-1]]:assert Image.open(p).size==(3840,2160)
 caption='Representative seeded time history | 750 N per bolt | Damping 2% | Motion magnified 50x | Playback slowed 273.07x'
 (O/'caption.txt').write_text(caption)
 title=f"Base {m['base']} | Instantaneous {m['response']} displacement\n{m['view_label']}\nSigned displacement [m]"
 if m.get('kind')=='stress':
  title='Base X | Dynamic von Mises stress\nPCB - unaveraged\nDynamic stress [Pa]'
  caption+=' | Static stress excluded'
  (O/'caption.txt').write_text(caption)
 (O/'title.txt').write_text(title)
 panel_width=1200 if (m.get('kind')=='stress' or m['view_label'].startswith('PCB')) else 850
 filt='[1:v]crop=%d:1300:0:0[legend];[0:v][legend]overlay=0:0:shortest=1[base];[base]'%panel_width
 filt+="drawbox=x=0:y=0:w=850:h=425:color=0x242424:t=fill,drawtext=fontfile=/System/Library/Fonts/Supplemental/Arial.ttf:textfile="+str(O/'title.txt')+":expansion=none:fontcolor=white:fontsize=42:line_spacing=20:x=56:y=62,"
 filt+="drawbox=x=0:y=ih-170:w=iw:h=170:color=black@0.90:t=fill,drawtext=fontfile=/System/Library/Fonts/Supplemental/Arial.ttf:textfile="+str(O/'caption.txt')+":expansion=none:fontcolor=white:fontsize=40:x=48:y=h-133,"
 filt+="drawtext=fontfile=/System/Library/Fonts/Supplemental/Arial.ttf:text='Simulation time %{expr\\:1.00006103515625+n/16384} s  |  4K / 60 fps':fontcolor=white:fontsize=40:x=48:y=h-72[out]"
 dest=D/(name+'.mp4');tmp=dest.with_suffix('.encoding.mp4')
 args=[FF,'-hide_banner','-y','-framerate','60','-i',str(O/'frames/AnimationFrame%06d.png'),'-loop','1','-i',str(legend),'-filter_complex',filt,'-map','[out]','-frames:v','480','-an','-c:v','h264_videotoolbox','-allow_sw','0','-profile:v','high','-level:v','5.2','-b:v','80M','-maxrate','120M','-bufsize','240M','-pix_fmt','yuv420p','-r','60','-g','120','-tag:v','avc1','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-movflags','+faststart','-metadata','title='+title.replace('\n',' | '),'-metadata','comment=Native Mechanical 2026R1 animation of 480 actual MAPDL transient result sets. Fixed camera. Seeded PSD realization, relative displacement, 750 N/bolt, 2% damping, 50x motion, 273.07x slower. Contours are instantaneous fields, not RMS; stress clip excludes static preload stress.',str(tmp)]
 (O/'encode_command.json').write_text(json.dumps(args,indent=2))
 with (O/'encode.log').open('w') as f:subprocess.run(args,stdout=f,stderr=f,check=True)
 info=json.loads(subprocess.check_output([FP,'-v','error','-show_streams','-show_format','-of','json',str(tmp)]));s=info['streams'][0];assert(s['width'],s['height'],s['r_frame_rate'],int(s['nb_frames']))==(3840,2160,'60/1',480)
 subprocess.run([FF,'-v','error','-i',str(tmp),'-f','null','-'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
 assert not any(t in (O/'encode.log').read_text() for t in ['Stray %','Error','Failed'])
 tmp.replace(dest);info['format']['filename']=str(dest);(O/'ENCODED.json').write_text(json.dumps(info,indent=2))
 for p in (O/'frames').glob('*.bmp'):p.unlink()
 subprocess.run([FF,'-v','error','-y','-ss','1','-i',str(dest),'-frames:v','1','-vf','scale=1280:-1',str(dest.with_suffix('.jpg'))],check=True)
 print('ENCODED',dest,flush=True)
if __name__=='__main__':encode(sys.argv[1])

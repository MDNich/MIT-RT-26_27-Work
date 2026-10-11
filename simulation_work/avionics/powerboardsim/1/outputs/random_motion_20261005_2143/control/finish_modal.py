from pathlib import Path
import subprocess,zipfile,json,ast,math,shutil,hashlib
from PIL import Image,ImageDraw,ImageFont
T=Path(__file__).resolve().parents[1];P=T.parents[1];V=P/'outputs/video_4k60_20261005_1928';O=V/'modal_fig03_bolted_mode20';stage=T/'pilot_modal_dpf/final_export'
assert (T/'control/MODAL_RENDER_COMPLETE.txt').exists()
py=r'C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe';uuid='{e7540578-be7d-4ee0-9a40-8aa94dcb9efd}'
win=lambda p:r'Z:'+str(p).split('/Users/mdn',1)[1].replace('/','\\')
for attempt in range(3):
 copied=subprocess.run(['prlctl','exec',uuid,'--current-user','cmd.exe','/c','copy','/y',win(T/'control/collect_modal_native.py'),r'C:\Temp\collect_modal_native.py'],capture_output=True)
 if copied.returncode==0:break
else:raise RuntimeError('Native collector could not be staged')
dest=r'\\Mac\Home'+str(stage).split('/Users/mdn',1)[1].replace('/','\\')
subprocess.run(['prlctl','exec',uuid,py,r'C:\Temp\collect_modal_native.py',dest],check=True)
audits=[ast.literal_eval(x) for x in (stage/'field_audit.txt').read_text().splitlines()];assert len(audits)==180
for i,a in enumerate(audits):
 assert a['frame']==i and abs(a['phase_factor']-math.sin(2*math.pi*i/180))<1e-12
 assert abs(a['normalized_maximum']-7.160033972903191)<1e-5
if (O/'native_frames').exists() and not (O/'rejected_viewport_frames').exists():(O/'native_frames').rename(O/'rejected_viewport_frames')
if (O/'sequence').exists():
 quarantine=O/'rejected_viewport_sequence'
 if quarantine.exists():shutil.rmtree(O/'sequence')
 else:(O/'sequence').rename(quarantine)
(O/'native_frames').mkdir(exist_ok=True)
with zipfile.ZipFile(stage/'frames_png.zip') as z:z.extractall(O/'native_frames')
for name in ['FRAMES_VALIDATED.json','field_audit.txt','camera_audit.txt']:shutil.copy2(stage/name,O/name)
shutil.copy2(T/'control/render_modal.py',O/'explicit_phase_export.py')
colors=[(255,0,0),(255,158,0),(255,238,0),(203,255,0),(79,255,0),(0,255,79),(0,255,204),(0,238,255),(0,158,255),(0,0,255)]
im=Image.open(stage/'legend_verified.png').convert('RGB');column={im.getpixel((80,y)) for y in range(im.height)};assert all(c in column for c in colors)
out=Image.new('RGB',(3840,2160),(36,36,36));d=ImageDraw.Draw(out);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',42)
d.multiline_text((56,62),'Modal | Six 750 N bolts\nMode 20 | 2364.179 Hz\nNormalized displacement magnitude\nArbitrary visible peak: 3 mm',font=font,fill='white',spacing=20)
x,y,w,h=56,470,56,62
for i,c in enumerate(colors):d.rectangle((x,y+i*h,x+w,y+(i+1)*h),fill=c)
d.rectangle((x,y,x+w,y+10*h),outline='white',width=2)
for i in range(11):d.text((145,y+i*h-23),format(7.160033972903191*(1-i/10),'.5g'),font=font,fill='white')
out.save(O/'legend_source.png');(O/'COMPLETE.txt').write_text('180 accepted native 4K explicit phase frames.\n')
subprocess.run(['/Users/mdn/miniforge3/bin/python3',str(V/'control/encode.py'),O.name],check=True)
subprocess.run(['/Users/mdn/miniforge3/bin/python3',str(T/'control/build_legacy_gallery.py')],check=True)
print('MODAL READY',flush=True)

from pathlib import Path
import json,shutil,hashlib,zipfile
T=Path(__file__).resolve().parents[1];P=T.parents[1];V=P/'outputs/video_4k60_20261005_1928';M=P/'output/latex/modal_reproduction';R=P/'output/latex/random_vibration'
def cp(src,rel):
 if src.exists():
  dst=M/'videos'/rel;dst.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(src,dst)
for name in ['modal_fig01_default_mode01','modal_fig02_default_mode20','modal_fig03_bolted_mode20']:
 if not(V/name/'ENCODED.json').exists():continue
 for f in ['export.py','explicit_phase_export.py','audit.txt','FRAMES_VALIDATED.json','field_audit.txt','camera_audit.txt','ENCODED.json','encode_command.json']:
  if name=='modal_fig03_bolted_mode20' and f=='export.py':continue
  cp(V/name/f,Path(name)/f)
for f in ['render_modal.py','pcb_modal_motion_v5.py','modal_gui_pilot_v5.py','bmp_pilot.py','restore_v5.py','compare_warp_native1000.py','collect_modal_native.py','finish_modal.py']:cp(T/'control'/f,Path('scripts')/f)
cp(V/'control/encode.py',Path('scripts/encode.py'));cp(V/'control/paths.py',Path('scripts/paths.py'))
cp(T/'GRAPHICS_SCALE_ACCEPTED.json',Path('mode20_audits/GRAPHICS_SCALE_ACCEPTED.json'))
cp(T/'MOTION_PILOT_ACCEPTED.json',Path('mode20_audits/MOTION_PILOT_ACCEPTED.json'))
for f in ['FIELDS_ACCEPTED.json','dpf_nodes.json','native_audit.txt']:cp(T/'pilot_modal_dpf'/f,Path('mode20_audits')/f)
(M/'videos/README.txt').write_text('''Companion modal videos: three native 4K/60 fps clips.
See section 12 of the modal report. Each final clip contains three repetitions
of a 180-frame normalized cycle: 540 frames, 9 s. Movie time and amplitude are
not physical. The new bolted mode-20 export uses explicit DPF phase fields and
Mechanical PNGs; the two retained default-mode clips use native animation.
The preserved default results were not re-solved against the bolted model.
Large binary result files and native PNGs remain in the project archives.
''')
for root in [M,R/'reproduction']:
 f=root/'MANIFEST.json';data=json.loads(f.read_text());data['documentation_revision']='2026-10-06';old={k:v for k,v in data.get('files',{}).items() if (root/k).is_file()}
 for p in root.rglob('*'):
  if not p.is_file() or p==f:continue
  rel=p.relative_to(root).as_posix();rec=old.get(rel,{});rec['bytes']=p.stat().st_size;rec['sha256']=hashlib.file_digest(p.open('rb'),'sha256').hexdigest();old[rel]=rec
 data['files']=old;f.write_text(json.dumps(data,indent=2))
for src in [P/'output/latex/power_board_modal_comparison.pdf',R/'power_board_random_vibration.pdf']:shutil.copy2(src,P/'output/pdf'/src.name)
# ZIP layout keeps the long-standing reproduction/ paths in the modal report.
for kind in ['modal_comparison','random_vibration']:
 dest=P/'output'/('power_board_'+kind+'_latex.zip');tmp=dest.with_suffix('.building.zip')
 with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  if kind=='modal_comparison':
   prefix=Path('power_board_'+kind)
   if dest.exists():
    with zipfile.ZipFile(dest) as oldzip:
     for n in oldzip.namelist():
      if '/reproduction/' not in n and not n.endswith(('.tex','.pdf')) and not n.endswith('/'):z.writestr(n,oldzip.read(n))
   for suffix in ['tex','pdf']:z.write(P/'output/latex'/('power_board_'+kind+'.'+suffix),prefix/('power_board_'+kind+'.'+suffix))
   for f in M.rglob('*'):
    if f.is_file():z.write(f,prefix/'reproduction'/f.relative_to(M))
  else:
   for f in R.rglob('*'):
    if f.is_file() and (f.parent!=R or f.suffix not in ['.aux','.log','.out','.toc']) and not any(part.startswith('.') or part=='__pycache__' for part in f.relative_to(R).parts):z.write(f,Path('power_board_'+kind)/f.relative_to(R))
 assert zipfile.ZipFile(tmp).testzip() is None
 tmp.replace(dest);print(dest,dest.stat().st_size)

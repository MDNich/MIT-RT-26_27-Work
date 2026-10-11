import sys,json,shutil,zipfile,datetime,hashlib,csv
from pathlib import Path
sys.path.insert(0,'/tmp')
from rv_paths import *
import package_powerboard_reproduction as pkg
E=Path((P/'output/latest_english_figures.txt').read_text())
D=P/'output/latex/random_vibration';MD=P/'output/latex/modal_reproduction'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
rows=list(csv.DictReader((E/'export_audit.tsv').read_text().splitlines(),delimiter='\t'))
assert len(rows)==20 and len({r['file'] for r in rows})==20
for aid,src in [(4182,OLD/'default_refined/frequencies.csv'),(1656,OLD/'bolted750_modal/frequencies.csv')]:
 original=list(csv.DictReader(src.read_text().splitlines()))
 actual=[float(x) for x in (E/('modal_frequencies_'+str(aid)+'.txt')).read_text().splitlines()]
 assert len(original)==len(actual)==20
 assert all(abs(float(a['frequency_hz'])-b)<1e-9 for a,b in zip(original,actual))
assert pkg.sha(E/'AssemblyBack.png')==pkg.sha(D/'figures/AssemblyBack.png')
for kind,stem,srcdir,root in [('modal','power_board_modal_comparison',P/'output/latex',MD),('random','power_board_random_vibration',D,D/'reproduction')]:
 pkg.build(root,kind)
 for f in ['export_english_figures.py','translate_workbench_titles.py','refit_back_view.py']:pkg.add(root,E/f,'scripts/'+f)
 for f in ['export_audit.tsv','caption_translation_audit.txt','modal_frequencies_1656.txt','modal_frequencies_4182.txt','COMPLETE.txt']:
  pkg.add(root,E/f,'common/english_figures/'+f)
 if kind=='modal':
  for f in ['DefaultFirst.png','DefaultTwentieth.png','BoltedTwentieth.png']:pkg.add(root,E/f,'english_figures/'+f)
 manifest=json.loads((root/'MANIFEST.json').read_text());manifest['files']=pkg.sources[str(root)];manifest['english_figure_revision_utc']=now
 (root/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
 srcpdf=srcdir/(stem+'.pdf');dstpdf=P/'output/pdf'/(stem+'.pdf');shutil.copy2(srcpdf,dstpdf)
 metadata={'updated_utc':now,'all_mechanical_figures_regenerated_in_english':True,'native_mechanical_exports':3 if kind=='modal' else 17,'numerical_results_changed':False,'new_simulation_run':False,'modal_frequencies_verified':40,'qa':'All 20 native figures checked visually and by OCR; changed PDF pages rendered and reviewed. Remaining pages match previous PDF renders pixel-for-pixel. No overfull boxes or LaTeX warnings; inherited benign underfull paragraph remains.','pages':pkg.pages(dstpdf),'pdf_sha256':pkg.sha(dstpdf),'figure_audit':'reproduction/common/english_figures/export_audit.tsv','study_caption_translation_audit':'reproduction/common/english_figures/caption_translation_audit.txt','back_camera_scene_height_multiplier':1.25}
 if kind=='random':
  path=D/'verification_summary.json';old=json.loads(path.read_text());old['english_figure_revision']=metadata;old['pdf_pages']=metadata['pages'];old['pdf_sha256']=metadata['pdf_sha256'];old['pdf_visual_qa']=metadata['qa'];path.write_text(json.dumps(old,indent=2))
  readme=D/'README.txt'
 else:
  (MD/'verification_summary.json').write_text(json.dumps(metadata,indent=2));readme=MD/'README.txt'
 with readme.open('a') as stream:stream.write('\nENGLISH FIGURE REVISION\nAll report Mechanical images were re-exported in English, including the\nWorkbench study headings. Numerical results are unchanged. Translation\nand export scripts and their audits are bundled. The original result\narchives remain intact. The straight Back view includes a 1.25 fit margin.\n')
 with zipfile.ZipFile(P/'output'/(stem+'_latex.zip'),'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  z.write(srcdir/(stem+'.tex'),stem+'/'+stem+'.tex');z.write(srcpdf,stem+'/'+stem+'.pdf')
  if kind=='modal':
   z.write(P/'output/power_board_modal_frequencies.csv',stem+'/power_board_modal_frequencies.csv')
   for f in sorted(MD.rglob('*')):
    if f.is_file():z.write(f,stem+'/reproduction/'+str(f.relative_to(MD)))
  else:
   for f in sorted(D.rglob('*')):
    if not f.is_file() or f in [D/(stem+'.tex'),srcpdf]:continue
    if f.parent==D and f.suffix in ['.aux','.log','.out','.toc','.synctex']:continue
    z.write(f,stem+'/'+str(f.relative_to(D)))
 print(kind,metadata['pages'],'pages, source bundle updated')
(E/'report_revision_verification.json').write_text(json.dumps({'updated_utc':now,'native_exports':20,'frequency_values_unchanged':40,'no_new_solve':True,'reports':['output/pdf/power_board_modal_comparison.pdf','output/pdf/power_board_random_vibration.pdf']},indent=2))
shutil.copy2('/tmp/package_english_reports.py',P/'output/reproduction_tools/package_english_reports.py')

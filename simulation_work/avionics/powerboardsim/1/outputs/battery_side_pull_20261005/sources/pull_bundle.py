from pull_paths import *
import json,hashlib,shutil,zipfile
B=P/'output/battery_side_pull_source';B.mkdir(exist_ok=True)
L=P/'output/latex/battery_side_pull'
for rel in ['latex/figures','latex/plots','latex/data','cases','audit','procedure']:(B/rel).mkdir(parents=True,exist_ok=True)
for p in L.rglob('*'):
 if p.is_file() and p.suffix in ['.tex','.png','.csv']:
  q=B/'latex'/p.relative_to(L);q.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(p,q)
accepted=sorted(p.parent for p in (S/'runtime').glob('*/ACCEPTED.json'))
files=['run.dat','model.inp','preflight.dat','post_corrected.dat','config.json','mesh.json','input_sha256.json','ACCEPTED.json','PREFLIGHT_PASSED.txt','SOLVE_STARTED.txt','inventory.txt','history.csv','nodal.csv','element_top.csv','element_bottom.csv','balance.csv','contact_history.csv','contact_detail.csv','moment_balance.csv','moment_balance_battery_centre.csv','preload_lock.csv','run.out','pull.err','preflight.out','check.err','post_corrected.out','post.err']
for d in accepted:
 q=B/'cases'/d.name;q.mkdir(exist_ok=True)
 for f in files:
  if (d/f).exists():shutil.copy2(d/f,q/f)
for p in (S/'audit').glob('*'):
 if p.suffix in ['.json','.tsv','.txt'] and p.name not in ['queue.json','VM_BLOCKED.json','languagesettings_before.txt','static_api.txt']:
  shutil.copy2(p,B/'audit'/p.name)
for p in (S/'sources').glob('*provenance*.json'):shutil.copy2(p,B/'audit'/p.name)
for p in (S/'results').glob('*.json'):shutil.copy2(p,B/'audit'/p.name)
if (P/'output/pdf/power_board_battery_side_pull.pdf').exists():shutil.copy2(P/'output/pdf/power_board_battery_side_pull.pdf',B/'power_board_battery_side_pull.pdf')
# Portable auditor takes the case directory directly; no host/VM connection needed.
s=Path('/tmp/pull_audit.py').read_text().replace('from pull_paths import *','from pathlib import Path').replace("case=sys.argv[1];D=S/'runtime'/case;cfg=", "D=Path(sys.argv[1]).resolve();case=D.name;cfg=")
(B/'procedure/audit_case.py').write_text(s)
(B/'README.txt').write_text('''Power board - edge battery lateral pull. Issued 5 October 2026.

This is an exploratory local deformation study. There is no calibrated tearing
law and no qualified breaking load. Read the report assumptions before reuse.

latex/ contains the editable report, external PNGs, native PGFPlots and CSVs.
cases/ contains the accepted as-run decks, native logs and exported results.
audit/ records geometry, material sources, checks and excluded-attempt diagnosis.
procedure/audit_case.py is a portable NumPy-based audit of a solved case folder.
SHA256.json hashes every file included except the manifest itself.

REPRODUCTION
1. Make a NEW local run folder. Copy run.dat, preflight.dat,
   post_corrected.dat, config.json and mesh.json from one accepted case.
2. Use MAPDL 2026 R1.02 (26.1 UP20260202); units are N, mm and MPa.
3. Run the one-line commands below from that fresh folder using ANSYS261.exe:
   -b nolist -s noread -smp -np 1 -p preppost -j check -i preflight.dat -o preflight.out
   Check zero errors and the inventory before any solve.
   -b nolist -s noread -smp -np 4 -p ansys -j pull -i run.dat -o run.out
   Wait for native completion; do not rerun in the same folder after a failure.
   -b nolist -s noread -smp -np 1 -p preppost -j post -i post_corrected.dat -o post_corrected.out
   The postprocessor reads solved.db and pull.rst; it does not solve.
   If the pre/post seat is occupied, -p ansys is also valid for this read-only stage.
4. Run python audit_case.py <fresh-case-folder> with Python and NumPy.
   Check zero errors, target endpoint, equilibrium, constant clamp UZ during pull,
   and the 750 N transfer where applicable. Review all warnings.
5. Compare the native CSVs against the provided case exports.
6. From latex/, run pdflatex power_board_battery_side_pull.tex twice.

Large RST/DB binary files and full vendor publications are not included in this
bundle. Rerunning the included decks recreates the numerical binaries. Original
binaries and stopped-attempt data remain in outputs/battery_side_pull_20261005.
The source assembly CAD itself is not included in this bundle.
''')
manifest={str(p.relative_to(B)):hashlib.sha256(p.read_bytes()).hexdigest() for p in B.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(B/'SHA256.json').write_text(json.dumps(manifest,indent=2))
zipname=P/'output/power_board_battery_side_pull_source.zip'
with zipfile.ZipFile(zipname,'w',zipfile.ZIP_DEFLATED) as z:
 for p in B.rglob('*'):
  if p.is_file():z.write(p,Path('battery_side_pull_source')/p.relative_to(B))
print('Accepted cases:',[p.name for p in accepted]);print('Bundle',zipname,'bytes',zipname.stat().st_size)

from pathlib import Path
import csv, hashlib, json, re
R=Path(__file__).resolve().parent
cases=['default','default_refined','bolted750_modal']
report={}
for name in cases:
 p=R/name
 if not (p/'RESULTS_VERIFIED.txt').exists(): continue
 frequencies=[float(row['frequency_hz']) for row in csv.DictReader((p/'frequencies.csv').open())]
 assert len(frequencies)==20 and frequencies==sorted(frequencies) and min(frequencies)>=1
 log=(p/'solve.out').read_text(errors='replace')
 assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s+0',log),name
 tail=log.split('FREQUENCIES FROM BLOCK LANCZOS ITERATION')[-1]
 found=re.findall(r'^\s+(\d+)\s+([0-9.]+(?:[EeDd][+-]?\d+)?)\s*$',tail,re.M)[:20]
 assert [int(x[0]) for x in found]==list(range(1,21)),(name,found)
 assert all(abs(float(v)-f)<1e-6 for (_,v),f in zip(found,frequencies)),name
 inp=(p/'ds.dat').read_text(errors='replace')
 assert re.search(r'modopt,lanb,20,1(?:\.|,),',inp,re.I),name
 files={}
 for f in [p/'ds.dat',p/'solve.out',p/'file.rst',p/'frequencies.csv']:
  h=hashlib.sha256()
  with f.open('rb') as stream:
   for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
  files[f.name]={'bytes':f.stat().st_size,'sha256':h.hexdigest()}
 report[name]={'frequency_hz':frequencies,'evidence':files,'zero_solver_errors':True,'native_log_matches_result_reader':True}
(R/'accepted_results_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('Verified:',', '.join(report))

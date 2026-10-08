from rv_paths import *
import csv,re,json,hashlib
C=R/'modal_basis'
assert (C/'MODAL_VERIFIED.txt').exists()
s=(C/'solve.out').read_text(errors='replace')
assert re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0',s)
assert 'time = 2 (load step = 2, substep = 4)' in s
assert len(re.findall(r'FIXED RELATIVE MOTION=',s))>=6
assert 'mxpand,,,,yes,,yes' in (C/'ds.dat').read_text().lower()
f=[float(x['frequency_hz']) for x in csv.DictReader((C/'frequencies.csv').open())]
old=[float(x['frequency_hz']) for x in csv.DictReader((OLD/'bolted750_modal/frequencies.csv').open())]
assert len(f)==38 and 3000<f[-1]<=4000
relative=max(abs(a-b)/b for a,b in zip(f[:20],old))
assert relative<1e-6
masses={}
for axis in ['X','Y','Z']:
 z=re.search(r'PARTICIPATION FACTOR CALCULATION \*+\s+'+axis+r'\s+DIRECTION(.*?)(?:PARTICIPATION FACTOR CALCULATION|MODAL MASSES)',s,re.S)
 assert z
 rows=[]
 for line in z.group(1).splitlines():
  v=line.split()
  if len(v)==8 and v[0].isdigit():rows.append([float(x) for x in v])
 assert len(rows)==38
 masses[axis]=sum(row[-1] for row in rows)
 with (C/('participation_'+axis+'.csv')).open('w') as file:
  w=csv.writer(file);w.writerow(['mode','frequency_hz','period_s','participation','relative_participation','effective_mass_kg','fraction_of_extracted_mass','fraction_of_total_mass']);w.writerows(rows)
manifest={'modal_analysis_id':4254,'count':len(f),'minimum_hz':min(f),'maximum_hz':max(f),'first20_max_relative_change':relative,'effective_mass_fraction':masses,'errors':0,'warning_count':int(re.search(r'NUMBER OF WARNING\s+MESSAGES ENCOUNTERED=\s*(\d+)',s)[1]),'parent':'static 4123, time2, loadstep2,substep4','bolts':'six locked pretension sections','input_sha256':hashlib.sha256((C/'ds.dat').read_bytes()).hexdigest(),'solve_sha256':hashlib.sha256((C/'solve.out').read_bytes()).hexdigest()}
(C/'audit.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))

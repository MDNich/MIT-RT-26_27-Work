from pathlib import Path
import csv,json
R=Path(__file__).resolve().parent
assert (R/'bolted750_refined/STATIC_VERIFIED.txt').exists()
assert (R/'bolted750_modal/RESULTS_VERIFIED.txt').exists()
audit=json.loads((R/'accepted_results_audit.json').read_text())
assert len(audit)==3
cases=['default','default_refined','bolted750_modal']
rows=[[i+1]+[audit[c]['frequency_hz'][i] for c in cases] for i in range(20)]
output=R.parents[2]/'output';output.mkdir(exist_ok=True)
with (output/'power_board_modal_frequencies.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['rank','original_default_hz','refined_default_hz','six_bolts_750N_hz']);w.writerows(rows)
C=json.loads((R/'report_content.json').read_text())
C['frequency_rows']=[[str(r[0])]+['%.3f'%x for x in r[1:]] for r in rows]
force_rows=list(csv.DictReader((R/'bolted750_refined/bolt_preload_audit.csv').open()))
locked=[r for r in force_rows if int(float(r['step']))==2]
assert len(locked)==6
locations=['Left / upper','Centre / upper','Right / upper','Left / lower','Centre / lower','Right / lower']
C['bolt_rows']=[[locations[int(float(r['bolt']))-1],'750.000','%.3f'%abs(float(r['reaction_N']))] for r in locked]
(R/'report_content.json').write_text(json.dumps(C,indent=2)+'\n')
print(output/'power_board_modal_frequencies.csv')

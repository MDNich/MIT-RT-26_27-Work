from rv_paths import *
import sys,csv,json,math
axis=sys.argv[1]
rows=list(csv.DictReader((R/axis/'result_summary.tsv').open(),delimiter='\t'))
assert len(rows)==17
pcb_nodes={int(v) for v in (R/'pcb_nodes.txt').read_text().split()}
pcb_elements={int(v) for v in (R/'pcb_elements.txt').read_text().split()}
mount={int(v) for v in (R/'mounting_nodes.txt').read_text().split()}
audit={};support={};hotspots={}
for row in rows:
 name=row['name'];p=R/axis/('result_'+row['result_id']+'.txt')
 nodes=set();elements=set();n=0;vmax=-1.;where=None
 with p.open(encoding='cp1252') as f:
  header=f.readline()
  for line in f:
   cells=line.rstrip().split('\t');node=int(cells[0]);v=float(cells[-1].replace(',','.'))
   assert math.isfinite(v) and v>=0,(p,node,v)
   nodes.add(node);n+=1
   if len(cells)==3:elements.add(int(cells[1]))
   if v>vmax:vmax=v;where=cells[:-1]
   if name=='RMS absolute acceleration '+axis+' - base '+axis and node in mount:support[node]=v
 assert len(nodes)==(217704 if 'PCB' in name else 368754),(name,len(nodes))
 if 'PCB' in name:assert nodes==pcb_nodes
 if 'PCB' in name and elements:assert elements==pcb_elements,(name,len(elements))
 expected=float(row['maximum'].split()[0])
 assert abs(vmax/expected-1)<1e-4,(name,vmax,expected)
 audit[name]={'rows':n,'nodes':len(nodes),'elements':len(elements),'maximum':vmax,'maximum_location':where}
 if 'equivalent stress' in name:hotspots[name]={'node':int(where[0]),'element':int(where[1]),'value_pa':vmax}
assert set(support)==mount
expected=14.135613719133904*9.80665
assert all(abs(v/expected-1)<.002 for v in support.values())
(R/axis/'field_coverage_audit.json').write_text(json.dumps(audit,indent=2))
(R/axis/'support_response_audit.json').write_text(json.dumps({'nodes':len(support),'min_accel_m_s2':min(support.values()),'max_accel_m_s2':max(support.values()),'expected_m_s2':expected},indent=2))
(R/axis/'stress_hotspots.json').write_text(json.dumps(hotspots,indent=2))
print(axis,'17 complete finite fields verified; all 781 supports reproduce the specified RMS input.')
print(json.dumps(hotspots,indent=2))

"""Diagnostic connectivity after virtual removal of highly degraded shell summaries.
No solver elements are deleted, and the result is not evidence of a geometric crack.
"""
from pathlib import Path
import json,sys
import numpy as np
S=Path(__file__).resolve().parent.parent
case=sys.argv[1];D=S/'runtime'/case
assert not (D/'REJECTED_LOAD_HISTORY.json').exists(),'Rejected load history is diagnostic only'
assert (D/'LOAD_HISTORY_VERIFIED.json').exists(),'Require verified continuous load history'
assert (D/'ACCEPTED.json').exists() or (D/'CONVERGED_STATES_AUDIT.json').exists()
m=json.loads((D/'mesh.json').read_text())
xyz={int(k):v for k,v in m['nodes'].items()}
els=np.array(m['elements'],dtype=int);cent=np.array([[xyz[n] for n in el] for el in els]).mean(1)
h=np.atleast_1d(np.genfromtxt(D/'history.csv',delimiter=',',names=True))
out=[]
for row in h:
 j=int(row['step'])
 f=np.atleast_1d(np.genfromtxt(D/f'damage_{j}.csv',delimiter=',',names=True))
 mx=np.maximum.reduce([f['damage_top'],f['damage_mid'],f['damage_bot']])
 mn=np.minimum.reduce([f['damage_top'],f['damage_mid'],f['damage_bot']])
 imax=int(np.argmax(mx))
 parents={n:n for n in xyz}
 def root(n):
  while parents[n]!=n:
   parents[n]=parents[parents[n]];n=parents[n]
  return n
 for el in els[mn<.99]:
  roots=[root(int(n)) for n in el];r=roots[0]
  for z in roots[1:]:parents[z]=r
 paths=[]
 for low in [True,False]:
  attach=[n for n in m['attachment'] if (xyz[n][1]<60)==low]
  clamp=[n for n in m['clamp'] if (xyz[n][1]<60)==low]
  paths.append(bool(set(map(root,attach)) & set(map(root,clamp))))
 out.append(dict(step=j,ux_mm=float(row['ux_mm']),force_N=float(abs(row['fx_N'])),
  max_summary_damage=float(mx[imax]),max_damage_element=imax+1,
  max_damage_region=m['region'][imax],max_damage_centroid_mm=cent[imax].tolist(),
  elements_any_sample_d99=int(sum(mx>=.99)),elements_all_three_samples_d99=int(sum(mn>=.99)),
  path_from_battery_to_clamp_after_virtual_removal=paths))
 result=dict(case=case,qualification='Connectivity diagnostic on top/mid/bottom element summaries; not integration-point proof or geometric severance; virtual removal only, no FE deletion',
  criterion='Remove shell in graph only when all three sampled section summaries are >=0.99 damage',states=out)
(D/'path_assessment.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result['states'][-1],indent=2))
